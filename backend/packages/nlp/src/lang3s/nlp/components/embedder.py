import math
from dataclasses import dataclass
from typing import (
    Literal,
    NamedTuple,
    Optional,
)

import numpy as np
import torch
from numpy.typing import NDArray
from transformers import AutoTokenizer

from lang3s.core import config
from lang3s.core.typing_extras import SingletonMeta
from lang3s.ml.math_extras import normalize
from lang3s.nlp.models.embedding import Lang3sMultiObjectiveEmbeddingModel

embedding_dtype = np.float32


class Chunk(NamedTuple):
    input_ids: list[torch.Tensor]
    attention_mask: list[torch.Tensor]
    word_ids: list[int]
    sentence_index: int
    start: int
    end: int


@dataclass
class SentenceTokenMapping:
    token_count: int
    word_ids: list[int | None]


class ChunkResult(NamedTuple):
    chunks: list[Chunk]
    mapping: list[SentenceTokenMapping]


@dataclass
class EmbeddingResult:
    word_embeddings: list[NDArray[np.floating]]
    sentence_embeddings: list[NDArray[np.floating]]
    token_embeddings: list[NDArray[np.floating]]
    mapping: list[SentenceTokenMapping]

    def batch(self, start, end):
        return EmbeddingResult(
            word_embeddings=self.word_embeddings[start:end],
            sentence_embeddings=self.sentence_embeddings[start:end],
            token_embeddings=self.token_embeddings[start:end],
            mapping=self.mapping[start:end],
        )

    def padded_token_embeddings_with_mask(
        self,
    ) -> tuple[NDArray[np.floating], NDArray[np.bool_]]:
        token_embeddings = self.token_embeddings

        B = len(token_embeddings)
        T_lengths = [
            arr.shape[0] for arr in token_embeddings
        ]  # original subword lengths
        max_T = max(T_lengths)
        H = token_embeddings[0].shape[1]

        hidden = np.zeros((B, max_T, H))
        mask = np.full((B, max_T), False, dtype=np.bool_)
        for b, arr in enumerate(token_embeddings):
            t = arr.shape[0]
            hidden[b, :t] = arr
            mask[b, :t] = True

        return hidden, mask


def _aggregate_hidden_states(
    hidden_states: list[NDArray[np.floating]],
    lengths: list[int],
) -> list[np.ndarray]:
    """
    Aggregate last N hidden layers into a single token representation.
    Returns [chunk_len, hidden_size] for each chunk  numpy arrays on CPU.
    """
    last_hidden = np.mean(hidden_states, axis=0)
    out: list[np.ndarray] = []
    for j, length in enumerate(lengths):
        arr = last_hidden[j, :length, :].copy()
        out.append(arr)
    return out


def _token_to_word(
    token_emb: np.ndarray,  # [num_tokens, hidden]
    word_ids: list[Optional[int]],
    hidden_size: int,
    mode: Literal["first", "mean"],
) -> np.ndarray:
    num_tokens = token_emb.shape[0]
    if num_tokens == 0:
        return np.zeros((0, hidden_size))

    assert len(word_ids) == num_tokens, (
        f"token_to_word: word_ids length {len(word_ids)} != num_tokens {num_tokens}"
    )

    valid_word_ids = [w for w in word_ids if w is not None]
    if not valid_word_ids:
        return np.zeros((0, hidden_size))

    num_words = max(valid_word_ids) + 1
    word_arr = np.zeros((num_words, hidden_size), dtype=embedding_dtype)

    if mode == "first":
        seen = [False] * num_words
        for tok_idx, w in enumerate(word_ids):
            if w is None:
                continue
            if not seen[w]:
                word_arr[w] = token_emb[tok_idx]
                seen[w] = True

    else:
        accumulator: list[list[np.ndarray]] = [[] for _ in range(num_words)]
        for tok_idx, w in enumerate(word_ids):
            if w is None:
                continue
            accumulator[w].append(token_emb[tok_idx])

        for w in range(num_words):
            if not accumulator[w]:
                continue
            embs = np.stack(accumulator[w], axis=0).astype(embedding_dtype, copy=False)
            word_arr[w] = embs.mean(axis=0)

    return word_arr


class Embedder(metaclass=SingletonMeta):
    def __init__(
        self,
    ) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(config.EMBEDDING_MODEL)
        self.model = Lang3sMultiObjectiveEmbeddingModel(config.EMBEDDING_MODEL)
        self.model.eval()
        self._device = "cpu"
        for p in self.model.parameters():
            p.requires_grad = False

        self.max_length: int = self.tokenizer.model_max_length
        self.stride: int = min(32, math.floor(self.max_length / 3))

    def __call__(
        self,
        texts: list[str] | list[list[str]],
        is_split_into_words: bool = False,
        batch_size: Optional[int] = None,
        task: Literal["nli", "search"] = "nli",
    ) -> EmbeddingResult:
        if config.INFERENCE_DEVICE != self._device:
            self._device = config.INFERENCE_DEVICE
            self.model.to(self._device)

        if not texts:
            return EmbeddingResult(
                word_embeddings=[],
                sentence_embeddings=[],
                token_embeddings=[],
                mapping=[],
            )

        if task == "search":
            if isinstance(texts[0], list):
                texts = [[t.lower() for t in text] for text in texts]
            else:
                texts = [t.lower() for t in texts]

        chunk_result = self._chunk(
            texts,
            is_split_into_words=is_split_into_words,
        )
        return self._encode(chunk_result, batch_size=batch_size, task=task)

    def _chunk(
        self,
        texts: list[str] | list[list[str]],
        is_split_into_words: bool = False,
    ) -> ChunkResult:
        if not texts:
            return ChunkResult([], [])

        encodings = self.tokenizer(
            texts,
            truncation=False,
            padding=False,
            return_offsets_mapping=False,
            return_attention_mask=True,
            is_split_into_words=is_split_into_words,
        )

        all_chunks: list[Chunk] = []
        token_word_mapping: list[SentenceTokenMapping] = []

        # Ensure we always have list-of-sequences
        if isinstance(encodings["input_ids"][0], int):
            encodings["input_ids"] = [encodings["input_ids"]]
            encodings["attention_mask"] = [encodings["attention_mask"]]

        num_sentences = len(encodings["input_ids"])

        for sentence_index in range(num_sentences):
            input_ids = encodings["input_ids"][sentence_index]
            attn = encodings["attention_mask"][sentence_index]

            if hasattr(encodings, "encodings"):
                word_ids_for_encoding = encodings.encodings[sentence_index].word_ids
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
        task: Literal["nli", "search"] = "nli",
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

        chunk_frozen_tokens: list[np.ndarray] = []  # For NER (Layers 8-10)
        chunk_semantic_tokens: list[np.ndarray] = []  # For Words/Spans (Layer 12)
        final_sentence_embeddings: list[np.ndarray] = [
            np.zeros(config.SEMANTIC_EMBEDDING_DIMENSION)
            for _ in set([c.sentence_index for c in chunks])
        ]
        final_sentence_embeddings_counts: list[int] = [0] * len(
            set([c.sentence_index for c in chunks])
        )

        with torch.inference_mode():
            for i in range(0, len(chunks), bs):
                batch_chunks = chunks[i: i + bs]
                batch_inputs = self._build_batch_inputs(batch_chunks)

                outputs = self.model(**batch_inputs, task=task)

                last_hidden_state = outputs["semantic_head"]

                source_states = outputs["hidden_states"]
                hidden_states = [h.detach().cpu().numpy() for h in source_states[-5:]]

                lengths = [len(c.input_ids) for c in batch_chunks]
                compressor = outputs["compressor"]

                chunk_frozen_tokens.extend(
                    _aggregate_hidden_states(hidden_states, lengths)
                )

                semantic_np = last_hidden_state.detach().cpu().numpy()
                chunk_semantic_tokens.extend(
                    _aggregate_hidden_states([semantic_np], lengths)
                )

                mask = (
                    batch_inputs["attention_mask"]
                    .unsqueeze(-1)
                    .expand(last_hidden_state.size())
                    .float()
                )
                sum_embeddings = torch.sum(last_hidden_state * mask, 1)
                sum_mask = torch.clamp(mask.sum(1), min=1e-9)
                sent_768 = sum_embeddings / sum_mask
                sent_compressed = compressor(sent_768)
                sent_norm = torch.nn.functional.normalize(sent_compressed, p=2, dim=1)

                for c, e in zip(batch_chunks, sent_norm):
                    final_sentence_embeddings[c.sentence_index] += (
                        e.detach().cpu().numpy()
                    )
                    final_sentence_embeddings_counts[c.sentence_index] += 1

                del (
                    outputs,
                    batch_inputs,
                    last_hidden_state,
                    mask,
                    sum_embeddings,
                )
                del (
                    sent_768,
                    sent_compressed,
                    sent_norm,
                    sum_mask,
                    hidden_states,
                )

                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()

        token_embeddings, _ = self._dechunk(
            chunk_result=chunk_result,
            token_embeddings=chunk_frozen_tokens,
            create_word_embeddings=False,
        )

        _, raw_semantic_words = self._dechunk(
            chunk_result=chunk_result,
            token_embeddings=chunk_semantic_tokens,
            create_word_embeddings=True,
        )

        final_word_embeddings: list[np.ndarray] = []

        with torch.inference_mode():
            for doc_words in raw_semantic_words:
                if doc_words.shape[0] == 0:
                    final_word_embeddings.append(
                        np.zeros((0, config.SEMANTIC_EMBEDDING_DIMENSION)).astype(
                            embedding_dtype
                        )
                    )
                    continue

                words_tensor = torch.from_numpy(doc_words.astype(embedding_dtype)).to(
                    self._device
                )
                with torch.inference_mode():
                    words_compressed = compressor(words_tensor)
                words_norm = torch.nn.functional.normalize(words_compressed, p=2, dim=1)
                final_word_embeddings.append(words_norm.detach().cpu().numpy())

        for i in range(len(final_sentence_embeddings)):
            final_sentence_embeddings[i] = normalize(
                final_sentence_embeddings[i] / final_sentence_embeddings_counts[i]
            )

        return EmbeddingResult(
            token_embeddings=token_embeddings,  # 768-d (Frozen, good for NER)
            word_embeddings=final_word_embeddings,  # 368-d (Compressed, good for Spans)
            sentence_embeddings=final_sentence_embeddings,  # 368-d
            mapping=chunk_result.mapping,
        )

    def _build_batch_inputs(self, batch_chunks: list[Chunk]) -> dict[str, torch.Tensor]:
        padded = self.tokenizer.pad(
            {
                "input_ids": [c.input_ids for c in batch_chunks],
                "attention_mask": [c.attention_mask for c in batch_chunks],
            },
            return_tensors="pt",
        )
        return {k: v.to(self._device) for k, v in padded.items()}

    def _dechunk(
        self,
        chunk_result: ChunkResult,
        token_embeddings: list[np.ndarray],
        create_word_embeddings=False,
    ) -> tuple[list[NDArray[np.floating]], list[NDArray[np.floating]]]:
        if not token_embeddings:
            return [], []

        token_embeddings_per_doc = []
        orig_token_maps: list[list[Optional[int]]] = []
        for mapping in chunk_result.mapping:
            token_embeddings_per_doc.append(
                np.zeros(
                    (mapping.token_count, config.TOKEN_EMBEDDING_DIMENSION),
                    dtype=embedding_dtype,
                )
            )
            orig_token_maps.append(mapping.word_ids)

        mappings = chunk_result.mapping
        counts = [np.zeros(mapping.token_count, dtype=np.int16) for mapping in mappings]

        for chunk_meta, chunk_emb in zip(chunk_result.chunks, token_embeddings):
            doc_idx = chunk_meta.sentence_index
            start = chunk_meta.start
            end = start + len(chunk_meta.input_ids)
            token_embeddings_per_doc[doc_idx][start:end] += chunk_emb.astype(
                embedding_dtype
            )
            counts[doc_idx][start:end] += 1

        for doc_idx in range(len(token_embeddings_per_doc)):
            # Avoid division by zero
            view_counts = counts[doc_idx][:, np.newaxis]
            view_counts[view_counts == 0] = 1
            token_embeddings_per_doc[doc_idx] /= view_counts

        del counts

        if not create_word_embeddings:
            return token_embeddings_per_doc, []

        word_embeddings_per_doc: list[np.ndarray] = []
        for doc_idx, token_emb in enumerate(token_embeddings_per_doc):
            word_ids = orig_token_maps[doc_idx]
            if len(word_ids) == 0 or token_emb.shape[0] == 0:
                word_embeddings_per_doc.append(
                    np.zeros((0, config.TOKEN_EMBEDDING_DIMENSION)).astype(
                        embedding_dtype
                    )
                )
                continue

            assert len(word_ids) == token_emb.shape[0], (
                "word_ids length does not match num tokens after merge: "
                f"{len(word_ids)} vs {token_emb.shape[0]}"
            )

            word_arr = _token_to_word(
                token_emb,
                word_ids,
                hidden_size=config.TOKEN_EMBEDDING_DIMENSION,
                mode="first",
            )
            word_embeddings_per_doc.append(word_arr.astype(embedding_dtype))

        return (
            token_embeddings_per_doc,
            word_embeddings_per_doc,
        )
