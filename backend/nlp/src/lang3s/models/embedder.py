import json
import math
import os.path
import sys
from collections import defaultdict
from dataclasses import dataclass
# logger = Logger(__name__)
from typing import (
    DefaultDict,
    Dict,
    List,
    Literal,
    NamedTuple,
    Optional,
    Tuple,
    Union,
)

import numpy as np
import torch
from numpy.typing import NDArray
from torch import nn
from transformers import AutoModel, AutoTokenizer

import lang3s.config as config
from lang3s.maths import normalize
from lang3s.models.base_transformer_model import ForkedBaseModel
from lang3s.utils import decorators


class Chunk(NamedTuple):
    input_ids: List[torch.Tensor]
    attention_mask: List[torch.Tensor]
    word_ids: List[int]
    sentence_index: int
    start: int
    end: int


@dataclass
class SentenceTokenMapping:
    token_count: int
    word_ids: List[int | None]


class ChunkResult(NamedTuple):
    chunks: List[Chunk]
    mapping: List[SentenceTokenMapping]


@dataclass
class EmbeddingResult:
    word_embeddings: List[NDArray[np.floating]]
    sentence_embeddings: List[NDArray[np.floating]]
    token_embeddings: List[NDArray[np.floating]]
    mapping: List[SentenceTokenMapping]

    def batch(self, start, end):
        return EmbeddingResult(
            word_embeddings=self.word_embeddings[start:end],
            sentence_embeddings=self.sentence_embeddings[start:end],
            token_embeddings=self.token_embeddings[start:end],
            mapping=self.mapping[start:end],
        )

    def padded_token_embeddings_with_mask(
        self,
    ) -> Tuple[NDArray[np.floating], NDArray[np.bool]]:
        token_embeddings = self.token_embeddings

        B = len(token_embeddings)
        T_lengths = [
            arr.shape[0] for arr in token_embeddings
        ]  # original subword lengths
        max_T = max(T_lengths)
        H = token_embeddings[0].shape[1]

        hidden = np.zeros((B, max_T, H))
        mask = np.full((B, max_T), False, dtype=np.bool)
        for b, arr in enumerate(token_embeddings):
            t = arr.shape[0]
            hidden[b, :t] = arr
            mask[b, :t] = True

        return hidden, mask


def _aggregate_hidden_states(
    hidden_states: List[NDArray[np.floating]],
    lengths: List[int],
) -> List[np.ndarray]:
    """
    Aggregate last N hidden layers into a single token representation.
    Returns [chunk_len, hidden_size] for each chunk  numpy arrays on CPU.
    """
    last_hidden = np.mean(hidden_states, axis=0)
    out: List[np.ndarray] = []
    for j, length in enumerate(lengths):
        arr = last_hidden[j, :length, :]
        out.append(arr)
    return out


def _token_to_sentence(token_emb: NDArray[np.floating],
                       word_ids: List[Optional[int]]):
    if token_emb.shape[0] == 0:
        return np.zeros((token_emb.shape[-1],), dtype=np.float32)

    mask = np.array(
        [0.0 if w is None else 1.0 for w in word_ids], dtype=np.float32
    )
    if mask.sum() == 0:
        # no valid tokens, just average everything
        sent = token_emb.mean(axis=0).astype(np.float32, copy=False)
    else:
        mask = mask[:, None]  # [num_tokens, 1]
        weighted = token_emb.astype(np.float32, copy=False) * mask
        sent = weighted.sum(axis=0) / float(mask.sum())
    return normalize(sent)


def _token_to_word(
    token_emb: np.ndarray,  # [num_tokens, hidden]
    word_ids: List[Optional[int]],
    hidden_size: int,
    mode: Literal["first", "mean"]
) -> np.ndarray:
    num_tokens = token_emb.shape[0]
    if num_tokens == 0:
        return np.zeros((0, hidden_size))

    assert len(word_ids) == num_tokens, (
        f"token_to_word: word_ids length {len(word_ids)} "
        f"!= num_tokens {num_tokens}"
    )

    valid_word_ids = [w for w in word_ids if w is not None]
    if not valid_word_ids:
        return np.zeros((0, hidden_size))

    num_words = max(valid_word_ids) + 1
    word_arr = np.zeros((num_words, hidden_size))

    if mode == "first":
        seen = [False] * num_words
        for tok_idx, w in enumerate(word_ids):
            if w is None:
                continue
            if not seen[w]:
                word_arr[w] = token_emb[tok_idx]
                seen[w] = True

    else:
        accumulator: List[List[np.ndarray]] = [[] for _ in range(num_words)]
        for tok_idx, w in enumerate(word_ids):
            if w is None:
                continue
            accumulator[w].append(token_emb[tok_idx])

        for w in range(num_words):
            if not accumulator[w]:
                continue
            embs = np.stack(accumulator[w], axis=0).astype(
                np.float32, copy=False
            )
            word_arr[w] = embs.mean(axis=0)

    return word_arr


@decorators.singleton
class Embedder:
    """
    Long-sequence embedder with modular pooling.

    - Supports input longer than model max length via chunking + stride.
    - Produces:
        * token_embeddings: per tokenizer token
        * word_embeddings: per word (configurable token->word pooling)
        * sentence_embeddings: per sentence (mean pooling over tokens by default)
    """

    def __init__(
        self,
    ) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(config.EMBEDDING_MODEL)
        self.model = ForkedBaseModel(config.EMBEDDING_MODEL)
        self.model.eval()
        self._device = "cpu"

        for p in self.model.parameters():
            p.requires_grad = False

        self.max_length: int = self.tokenizer.model_max_length
        self.stride: int = min(32, math.floor(self.max_length / 3))

    def __call__(
        self,
        texts: Union[List[str], List[List[str]]],
        is_split_into_words: bool = False,
        batch_size: Optional[int] = None,
        task: Literal["nli", "search"] = "nli"
    ) -> EmbeddingResult:
        if config.INFERENCE_DEVICE != self._device:
            self._device = config.INFERENCE_DEVICE
            self.model.to(self._device)
            if hasattr(self, "compression_layer"):
                self.compression_layer.to(self._device)

        chunk_result = self._chunk(
            texts, is_split_into_words=is_split_into_words
        )
        return self._encode(chunk_result, batch_size=batch_size, task=task)

    def _chunk(
        self,
        texts: Union[List[str], List[List[str]]],
        is_split_into_words: bool = False,
    ) -> ChunkResult:
        encodings = self.tokenizer(
            texts,
            truncation=False,
            padding=False,
            return_offsets_mapping=False,
            return_attention_mask=True,
            is_split_into_words=is_split_into_words,
        )

        all_chunks: List[Chunk] = []
        token_word_mapping: List[SentenceTokenMapping] = []

        # Ensure we always have list-of-sequences
        if isinstance(encodings["input_ids"][0], int):
            encodings["input_ids"] = [encodings["input_ids"]]
            encodings["attention_mask"] = [encodings["attention_mask"]]

        num_sentences = len(encodings["input_ids"])

        for sentence_index in range(num_sentences):
            input_ids = encodings["input_ids"][sentence_index]
            attn = encodings["attention_mask"][sentence_index]

            if hasattr(encodings, "encodings"):
                word_ids_for_encoding = encodings.encodings[
                    sentence_index
                ].word_ids
            else:
                raise RuntimeError("Unable to obtain word_ids from tokenizer")

            word_ids_for_encoding = list(word_ids_for_encoding)
            assert len(word_ids_for_encoding) == len(input_ids), (
                "word_ids and input_ids length mismatch: "
                f"{len(word_ids_for_encoding)} vs {len(input_ids)}"
            )

            token_word_mapping.append(
                SentenceTokenMapping(
                    token_count=len(input_ids),
                    word_ids=word_ids_for_encoding,
                )
            )

            start = 0
            while start < len(input_ids):
                end = min(start + self.max_length, len(input_ids))
                all_chunks.append(
                    Chunk(
                        input_ids=input_ids[start:end],
                        attention_mask=attn[start:end],
                        sentence_index=sentence_index,
                        word_ids=word_ids_for_encoding[start:end],
                        start=start,
                        end=end,
                    )
                )
                if end == len(input_ids):
                    break
                start = end - self.stride if self.stride > 0 else end

        return ChunkResult(chunks=all_chunks, mapping=token_word_mapping)

    def _encode(
        self,
        chunk_result: ChunkResult,
        batch_size: Optional[int] = None,
        task: Literal["nli", "search"] = "nli"
    ) -> EmbeddingResult:
        chunks = chunk_result.chunks
        if not chunks:
            return EmbeddingResult(
                word_embeddings=[],
                sentence_embeddings=[],
                token_embeddings=[],
                mapping=chunk_result.mapping,
            )

        bs = batch_size or config.INFERENCE_BATCH_SIZE

        chunk_frozen_tokens: List[np.ndarray] = []  # For NER (Layers 8-10)
        chunk_semantic_tokens: List[np.ndarray] = []  # For Words/Spans (Layer 12)
        final_sentence_embeddings: List[np.ndarray] = []

        with torch.inference_mode():
            for i in range(0, len(chunks), bs):
                batch_chunks = chunks[i: i + bs]
                batch_inputs = self._build_batch_inputs(batch_chunks)

                outputs = self.model(**batch_inputs, task=task)
                hidden_states = outputs["hidden_states"][-5:].cpu().numpy()
                last_hidden_state = outputs["semantic_head"]
                compressor = outputs["compressor"]

                lengths = [len(c.input_ids) for c in batch_chunks]
                frozen_layers = [h for h in hidden_states]
                frozen_batch = _aggregate_hidden_states(frozen_layers, lengths)
                chunk_frozen_tokens.extend(frozen_batch)

                semantic_batch = _aggregate_hidden_states([last_hidden_state.cpu().numpy()], lengths)
                chunk_semantic_tokens.extend(semantic_batch)

                mask = batch_inputs['attention_mask'].unsqueeze(-1).expand(last_hidden_state.size()).float()
                sum_embeddings = torch.sum(last_hidden_state * mask, 1)
                sum_mask = torch.clamp(mask.sum(1), min=1e-9)
                sent_768 = sum_embeddings / sum_mask
                sent_compressed = compressor(sent_768)
                sent_norm = torch.nn.functional.normalize(sent_compressed, p=2, dim=1)

                final_sentence_embeddings.extend(sent_norm.cpu().float().numpy())

        token_embeddings, _ = self._dechunk(
            chunk_result=chunk_result,
            token_embeddings=chunk_frozen_tokens,
            create_word_embeddings=False
        )

        _, raw_semantic_words = self._dechunk(
            chunk_result=chunk_result,
            token_embeddings=chunk_semantic_tokens,
            create_word_embeddings=True
        )

        final_word_embeddings: List[np.ndarray] = []

        # We can batch this loop if you have massive documents, but per-doc is usually fine
        with torch.inference_mode():
            for doc_words in raw_semantic_words:
                if doc_words.shape[0] == 0:
                    final_word_embeddings.append(np.zeros((0, config.SEMANTIC_EMBEDDING_DIMENSION)))
                    continue

                words_tensor = torch.from_numpy(doc_words.astype(np.float32)).to(self._device)
                with torch.inference_mode():
                    words_compressed = compressor(words_tensor)
                words_norm = torch.nn.functional.normalize(words_compressed, p=2, dim=1)
                final_word_embeddings.append(words_norm.cpu().numpy())

        return EmbeddingResult(
            token_embeddings=token_embeddings,  # 768-d (Frozen, good for NER)
            word_embeddings=final_word_embeddings,  # 368-d (Compressed, good for Spans)
            sentence_embeddings=final_sentence_embeddings,  # 368-d
            mapping=chunk_result.mapping,
        )

    def _build_batch_inputs(
        self, batch_chunks: List[Chunk]
    ) -> Dict[str, torch.Tensor]:
        padded = self.tokenizer.pad(
            {
                "input_ids": [c.input_ids for c in batch_chunks],
                "attention_mask": [c.attention_mask for c in batch_chunks],
            },
            return_tensors="pt",
        )
        return {
            k: v.to(self._device) for k, v in padded.items()
        }

    def _dechunk(
        self,
        chunk_result: ChunkResult,
        token_embeddings: List[np.ndarray],
        create_word_embeddings=False
    ) -> Tuple[List[NDArray[np.floating]], List[NDArray[np.floating]]]:
        if not token_embeddings:
            return [], []

        # combined[doc_idx][token_pos] -> list of (embedding, weight)
        combined: DefaultDict[
            int, DefaultDict[int, List[Tuple[np.ndarray, float]]]
        ] = defaultdict(lambda: defaultdict(list))

        # 1) Reassign each chunk's tokens back into original positions
        for chunk_meta, chunk_emb in zip(
            chunk_result.chunks, token_embeddings
        ):
            b_idx = chunk_meta.sentence_index
            chunk_len = len(chunk_meta.input_ids)
            start_pos = chunk_meta.start

            for i in range(chunk_len):
                pos = start_pos + i
                weight = 1.0
                combined[b_idx][pos].append((chunk_emb[i], weight))

        token_embeddings_per_doc: List[np.ndarray] = []
        orig_token_maps: List[List[Optional[int]]] = []

        for doc_idx, mapping in enumerate(chunk_result.mapping):
            if doc_idx not in combined:
                token_embeddings_per_doc.append(np.zeros((0, config.TOKEN_EMBEDDING_DIMENSION)))
                orig_token_maps.append([])
                continue

            positions = sorted(combined[doc_idx].keys())
            num_tokens = mapping.token_count
            hidden_size = combined[doc_idx][positions[0]][0][0].shape[-1]

            merged = np.zeros((num_tokens, hidden_size))

            for pos in positions:
                emb_weight_list = combined[doc_idx][pos]
                if len(emb_weight_list) == 1:
                    merged[pos] = emb_weight_list[0][0]
                embs = np.stack([ew[0] for ew in emb_weight_list], axis=0)
                merged[pos] = embs.mean(axis=0)

            token_embeddings_per_doc.append(merged.astype(np.float32))
            orig_token_maps.append(mapping.word_ids)  # type:ignore

        if not create_word_embeddings:
            return token_embeddings_per_doc, []

        # Token -> word embeddings using pooling.token_to_word
        word_embeddings_per_doc: List[np.ndarray] = []
        for doc_idx, token_emb in enumerate(token_embeddings_per_doc):
            word_ids = orig_token_maps[doc_idx]

            if len(word_ids) == 0 or token_emb.shape[0] == 0:
                word_embeddings_per_doc.append(np.zeros((0, config.TOKEN_EMBEDDING_DIMENSION)))
                continue

            assert len(word_ids) == token_emb.shape[0], (
                "word_ids length does not match num tokens after merge: "
                f"{len(word_ids)} vs {token_emb.shape[0]}"
            )

            word_arr = _token_to_word(
                token_emb, word_ids, hidden_size=config.TOKEN_EMBEDDING_DIMENSION, mode="first"
            )
            word_embeddings_per_doc.append(word_arr.astype(np.float32))

        return token_embeddings_per_doc, word_embeddings_per_doc,
