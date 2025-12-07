import math
from collections import defaultdict
from logging import Logger
from typing import Dict, DefaultDict, Tuple
from typing import Optional, Union

from transformers import AutoModel, AutoTokenizer

import lang3s.config as config
from lang3s.maths import normalize
from lang3s.models.cls import ClsDetector
from lang3s.utils import decorators

logger = Logger(__name__)

from typing import List, Literal, NamedTuple

import numpy as np
import torch
from numpy.typing import NDArray


class Chunk(NamedTuple):
    input_ids: List[torch.Tensor]
    attention_mask: List[torch.Tensor]
    word_ids: List[int]
    sentence_index: int
    start: int
    end: int


class SentenceTokenMapping(NamedTuple):
    token_count: int
    word_ids: List[int | None]


class ChunkResult(NamedTuple):
    chunks: List[Chunk]
    mapping: List[SentenceTokenMapping]


class EmbeddingResult(NamedTuple):
    word_embeddings: List[NDArray[np.floating]]
    sentence_embeddings: List[NDArray[np.floating]]
    cls_embeddings: List[NDArray[np.floating]]
    token_embeddings: List[NDArray[np.floating]]
    mapping: List[SentenceTokenMapping]

    def batch(self, start, end):
        return EmbeddingResult(
            word_embeddings=self.word_embeddings[start:end],
            sentence_embeddings=self.sentence_embeddings[start:end],
            cls_embeddings=self.cls_embeddings[start:end],
            token_embeddings=self.token_embeddings[start:end],
            mapping=self.mapping[start:end]
        )

    def padded_token_embeddings_with_mask(self) -> Tuple[NDArray[np.floating], NDArray[np.bool]]:
        token_embeddings = self.token_embeddings

        B = len(token_embeddings)
        T_lengths = [arr.shape[0] for arr in token_embeddings]  # original subword lengths
        max_T = max(T_lengths)
        H = token_embeddings[0].shape[1]

        hidden = np.zeros((B, max_T, H))
        mask = np.full((B, max_T), False, dtype=np.bool)
        for b, arr in enumerate(token_embeddings):
            t = arr.shape[0]
            hidden[b, :t] = arr
            mask[b, :t] = True

        return hidden, mask


class DechunkedResult(NamedTuple):
    token_embeddings: List[NDArray[np.floating]]
    word_embeddings: List[NDArray[np.floating]]
    cls_embeddings: List[NDArray[np.floating]]


class PoolingConfig(NamedTuple):
    sentence_pool: Literal["mean", "cls"] = "mean"
    token_word_pool: Literal["first", "mean", "max"] = "first"
    phrase_pool: Literal["mean", "max", "mean_max_concat"] = "mean_max_concat"
    use_last_n_layers: int = 4  # for layer pooling


class Pooling:

    def __init__(self, cfg: PoolingConfig):
        self.cfg = cfg

    # ----- Sentence pooling -----

    def sentence(
        self,
        token_emb: np.ndarray,  # [num_tokens, hidden]
        word_ids: List[Optional[int]],
        cls_emb: Optional[np.ndarray] = None,  # [hidden]
    ) -> np.ndarray:
        """
        Pool token embeddings into a single sentence embedding.

        - "mean": mean over tokens with word_id != None
        - "cls":  use CLS embedding if provided, otherwise fallback to mean
        """
        if self.cfg.sentence_pool == "cls" and cls_emb is not None:
            return normalize(cls_emb.astype(np.float32, copy=False))

        # Default: mean over valid tokens (word_ids not None)
        if token_emb.shape[0] == 0:
            return np.zeros((token_emb.shape[-1],), dtype=np.float32)

        mask = np.array([0.0 if w is None else 1.0 for w in word_ids], dtype=np.float32)
        if mask.sum() == 0:
            # no valid tokens, just average everything
            sent = token_emb.mean(axis=0).astype(np.float32, copy=False)
        else:
            mask = mask[:, None]  # [num_tokens, 1]
            weighted = token_emb.astype(np.float32, copy=False) * mask
            sent = weighted.sum(axis=0) / float(mask.sum())
        return normalize(sent)

    def token_to_word(
        self,
        token_emb: np.ndarray,  # [num_tokens, hidden]
        word_ids: List[Optional[int]],
        hidden_size: int,
    ) -> np.ndarray:
        """
        Aggregate subword token embeddings into per-word embeddings.

        - "first": use first subword (best for NER/IOB)
        - "mean":  mean over subwords
        - "max":   max over subwords
        """
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

        mode = self.cfg.token_word_pool

        if mode == "first":
            seen = [False] * num_words
            for tok_idx, w in enumerate(word_ids):
                if w is None:
                    continue
                if not seen[w]:
                    word_arr[w] = token_emb[tok_idx]
                    seen[w] = True

        else:
            # accumulate lists for mean or max
            accumulator: List[List[np.ndarray]] = [[] for _ in range(num_words)]
            for tok_idx, w in enumerate(word_ids):
                if w is None:
                    continue
                accumulator[w].append(token_emb[tok_idx])

            for w in range(num_words):
                if not accumulator[w]:
                    continue
                embs = np.stack(accumulator[w], axis=0).astype(np.float32, copy=False)
                if mode == "mean":
                    word_arr[w] = embs.mean(axis=0)
                elif mode == "max":
                    word_arr[w] = embs.max(axis=0)
                else:
                    raise ValueError(f"Unsupported token_word_pool: {mode}")

        return word_arr

    def phrase(
        self,
        word_emb: np.ndarray,  # [num_words, hidden]
        start: int,
        end: int,
    ) -> np.ndarray:
        """
        Pool a span of word embeddings [start:end] into a phrase/entity embedding.

        Uses cfg.phrase_pool:
          - "mean": mean over span
          - "max":  max over span
          - "mean_max_concat": concat(mean, max) -> 2 * hidden_size
        """
        if start < 0 or end > word_emb.shape[0] or start >= end:
            raise ValueError(
                f"Invalid phrase span [{start}, {end}) for word_emb shape {word_emb.shape}"
            )

        span = word_emb[start:end].astype(np.float32, copy=False)
        mode = self.cfg.phrase_pool

        if span.shape[0] == 0:
            return np.zeros((word_emb.shape[-1],), dtype=np.float32)

        if mode == "mean":
            return normalize(span.mean(axis=0))

        if mode == "max":
            return normalize(span.max(axis=0))

        if mode == "mean_max_concat":
            mean_vec = span.mean(axis=0)
            max_vec = span.max(axis=0)
            concat = np.concatenate([mean_vec, max_vec], axis=-1)
            return normalize(concat)

        raise ValueError(f"Unsupported phrase_pool: {mode}")


@decorators.singleton
class Embedder:
    """
    Long-sequence embedder with modular pooling.

    - Supports input longer than model max length via chunking + stride.
    - Produces:
        * token_embeddings: per tokenizer token
        * word_embeddings: per word (configurable token->word pooling)
        * sentence_embeddings: per sentence (mean pooling over tokens by default)
        * cls_embeddings: optional CLS-aggregated embeddings per sentence
    - Provides phrase/entity embedding helper via phrase_pooling.
    """

    def __init__(
        self,
    ) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(config.EMBEDDING_MODEL)
        self.model = AutoModel.from_pretrained(
            config.EMBEDDING_MODEL,
            trust_remote_code=True,
        )
        self.model.eval()
        for p in self.model.parameters():
            p.requires_grad = False

        self.dimensions: int = self.model.config.hidden_size
        self.max_length: int = self.tokenizer.model_max_length
        self.stride: int = min(32, math.floor(self.max_length / 3))
        self._device: str = config.INFERENCE_DEVICE
        self.model.to(self._device)

        # Pooling configuration + helper
        self.pool_cfg = PoolingConfig(
            sentence_pool="mean",
            token_word_pool="first",
            phrase_pool="mean_max_concat",
        )
        self.pooling = Pooling(self.pool_cfg)
        self.cls_detector = ClsDetector(self.tokenizer, self.model)

    # ---------- Public API ----------

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, device: str):
        self._device = device
        self.model.to(self._device)

    def __call__(
        self,
        texts: Union[List[str], List[List[str]]],
        is_split_into_words: bool = False,
        agg: str = "mean",
        batch_size: Optional[int] = None,
    ) -> EmbeddingResult:
        """
        Entry point:
          texts: list of sentences or list of word-tokenized sentences
          is_split_into_words: if True, texts is List[List[str]]
          agg: 'weighted' | 'mean' | 'first' for overlapping chunk merge
        """
        chunk_result = self._chunk(texts, is_split_into_words=is_split_into_words)
        return self._encode(chunk_result, batch_size=batch_size, agg=agg)

    # Convenience: phrase/entity embedding helper (Option B)
    def phrase_embedding(
        self,
        word_embeddings: np.ndarray,
        start: int,
        end: int,
    ) -> np.ndarray:
        """
        Given per-word embeddings for a document/sentence and a word span [start:end),
        return a phrase/entity embedding using the configured phrase_pool.
        """
        return self.pooling.phrase(word_embeddings, start, end)

    # ---------- Chunking ----------

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

            word_ids_for_encoding = None
            if hasattr(encodings, "encodings"):
                word_ids_for_encoding = encodings.encodings[sentence_index].word_ids
            else:
                single = self.tokenizer(
                    texts[sentence_index],
                    is_split_into_words=is_split_into_words,
                    return_offsets_mapping=False,
                    return_attention_mask=False,
                    truncation=False,
                    padding=False,
                )
                if hasattr(single, "encodings"):
                    word_ids_for_encoding = single.encodings[0].word_ids

            if word_ids_for_encoding is None:
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

            # Sliding window chunking over token indices
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

        return ChunkResult(chunks=all_chunks,
                           mapping=token_word_mapping)

    # ---------- Encoding / Forward pass ----------

    def _encode(
        self,
        chunk_result: ChunkResult,
        agg: str,
        batch_size: Optional[int] = None,
    ) -> EmbeddingResult:
        chunks = chunk_result.chunks
        if not chunks:
            return EmbeddingResult(cls_embeddings=[],
                                   word_embeddings=[],
                                   sentence_embeddings=[],
                                   token_embeddings=[],
                                   mapping=chunk_result.mapping)

        bs = batch_size or config.INFERENCE_BATCH_SIZE

        chunk_token_outputs: List[np.ndarray] = []
        cls_outputs: List[np.ndarray] = []

        with torch.inference_mode():
            for i in range(0, len(chunks), bs):
                batch_chunks = chunks[i: i + bs]
                batch_inputs = self._build_batch_inputs(batch_chunks)

                outputs = self.model(
                    **batch_inputs,
                    output_hidden_states=True,
                )

                # CLS per chunk: tensor [batch, hidden]
                cls_emb_batch: torch.Tensor = self.cls_detector.get_cls_embedding(
                    batch_inputs,
                    outputs.last_hidden_state,
                )
                cls_outputs.extend(
                    cls_emb_batch.detach().cpu().numpy().astype(np.float32, copy=False)
                )

                # Token embeddings via mean over last N layers
                token_embs_batch = self._aggregate_hidden_states(
                    outputs.hidden_states,
                    [len(c.input_ids) for c in batch_chunks],
                )

                chunk_token_outputs.extend(token_embs_batch)

        # Dechunk back to full sentences / documents
        dechunked = self._dechunk(
            chunk_result=chunk_result,
            model_outputs=chunk_token_outputs,
            cls_embeddings=cls_outputs,
            agg=agg,
        )

        # Sentence embeddings: mean pooling over tokens (by default)
        sentence_embeddings: List[np.ndarray] = []
        for doc_idx, token_emb in enumerate(dechunked.token_embeddings):
            mapping = chunk_result.mapping[doc_idx]
            cls_emb = (
                dechunked.cls_embeddings[doc_idx]
                if 0 <= doc_idx < len(dechunked.cls_embeddings)
                else None
            )
            sent_vec = self.pooling.sentence(token_emb, mapping.word_ids, cls_emb=cls_emb)  # type:ignore
            sentence_embeddings.append(sent_vec)

        # Normalize word embeddings (optional but usually beneficial)
        norm_word_embeddings = [normalize(w) for w in dechunked.word_embeddings]

        return EmbeddingResult(
            token_embeddings=dechunked.token_embeddings,
            word_embeddings=norm_word_embeddings,
            sentence_embeddings=sentence_embeddings,
            mapping=chunk_result.mapping,
            cls_embeddings=dechunked.cls_embeddings,
        )

    def _build_batch_inputs(self, batch_chunks: List[Chunk]) -> Dict[str, torch.Tensor]:
        padded = self.tokenizer.pad(
            {
                "input_ids": [c.input_ids for c in batch_chunks],
                "attention_mask": [c.attention_mask for c in batch_chunks],
            },
            return_tensors="pt",
        )
        return {k: v.to(self.device, non_blocking=True) for k, v in padded.items()}

    def _aggregate_hidden_states(
        self,
        hidden_states: Tuple[torch.Tensor, ...],
        lengths: List[int],
    ) -> List[np.ndarray]:
        """
        Aggregate last N hidden layers into a single token representation.
        Returns [chunk_len, hidden_size] for each chunk  numpy arrays on CPU.
        """
        n_layers = min(self.pool_cfg.use_last_n_layers, len(hidden_states))
        if n_layers <= 0:
            last_hidden = hidden_states[-1]
        else:
            last_hidden = torch.stack(hidden_states[-n_layers:], dim=0).mean(dim=0)

        last_hidden = last_hidden.detach().cpu().numpy()

        out: List[np.ndarray] = []
        for j, length in enumerate(lengths):
            arr = last_hidden[j, :length, :]
            out.append(np.nan_to_num(arr, copy=False))
        return out

    # ---------- Dechunking ----------

    def _dechunk(
        self,
        chunk_result: ChunkResult,
        model_outputs: List[np.ndarray],  # per-chunk [chunk_len, hidden]
        cls_embeddings: List[np.ndarray],  # per-chunk [hidden]
        agg: str,
    ) -> DechunkedResult:
        if not model_outputs:
            return DechunkedResult([], [], [])

        stride = self.stride

        # combined[doc_idx][token_pos] -> list of (embedding, weight)
        combined: DefaultDict[int, DefaultDict[int, List[Tuple[np.ndarray, float]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        cls_tokens: DefaultDict[int, List[np.ndarray]] = defaultdict(list)

        # 1) Reassign each chunk's tokens back into original positions
        for chunk_meta, chunk_emb, cls_emb in zip(
            chunk_result.chunks, model_outputs, cls_embeddings
        ):
            b_idx = chunk_meta.sentence_index
            chunk_len = len(chunk_meta.input_ids)
            start_pos = chunk_meta.start
            end_pos = chunk_meta.end
            cls_tokens[b_idx].append(cls_emb)

            for i in range(chunk_len):
                pos = start_pos + i
                weight = 1.0

                if agg == "weighted":
                    # Taper weights for overlapping regions
                    if start_pos > 0 and i < stride:
                        weight = 0.5 + 0.5 * (i / max(stride, 1))
                    elif end_pos < chunk_result.mapping[b_idx].token_count and i >= chunk_len - stride:
                        dist_from_end = (chunk_len - 1) - i
                        weight = 0.5 + 0.5 * (dist_from_end / max(stride, 1))

                combined[b_idx][pos].append((chunk_emb[i], weight))

        # 2) Aggregate CLS per document
        max_doc_idx = max(cls_tokens.keys()) if cls_tokens else -1
        cls_tokens_per_doc: List[np.ndarray] = [None] * (max_doc_idx + 1)  # type:ignore
        for doc_idx, tokens in cls_tokens.items():
            cls_mean = np.mean(np.stack(tokens, axis=0), axis=0)
            cls_tokens_per_doc[doc_idx] = normalize(
                cls_mean.astype(np.float32, copy=False)
            )

        # 3) Merge token embeddings per doc
        token_embeddings_per_doc: List[np.ndarray] = []
        orig_token_maps: List[List[Optional[int]]] = []

        for doc_idx, mapping in enumerate(chunk_result.mapping):
            if doc_idx not in combined:
                token_embeddings_per_doc.append(
                    np.zeros((0, self.dimensions))
                )
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

                elif agg == "mean":
                    embs = np.stack([ew[0] for ew in emb_weight_list], axis=0)
                    merged[pos] = embs.mean(axis=0)

                elif agg == "first":
                    merged[pos] = emb_weight_list[0][0]

                elif agg == "weighted":
                    embs = np.stack([ew[0] for ew in emb_weight_list], axis=0)
                    weights = np.array(
                        [ew[1] for ew in emb_weight_list]
                    )
                    weights = weights[:, None]  # [k, 1]

                    weighted_sum = (embs * weights).sum(axis=0)
                    sum_of_weights = float(weights.sum())
                    if sum_of_weights > 0:
                        merged[pos] = (weighted_sum / sum_of_weights)
                    else:
                        merged[pos] = embs[0]

                else:
                    raise ValueError("agg must be one of: 'mean', 'first', 'weighted'")

            token_embeddings_per_doc.append(merged)
            orig_token_maps.append(mapping.word_ids)  # type:ignore

        # 4) Token -> word embeddings using pooling.token_to_word
        word_embeddings_per_doc: List[np.ndarray] = []
        for doc_idx, token_emb in enumerate(token_embeddings_per_doc):
            word_ids = orig_token_maps[doc_idx]

            if len(word_ids) == 0 or token_emb.shape[0] == 0:
                word_embeddings_per_doc.append(
                    np.zeros((0, self.dimensions))
                )
                logger.warning("No word ids found during dechunking")
                continue

            assert len(word_ids) == token_emb.shape[0], (
                "word_ids length does not match num tokens after merge: "
                f"{len(word_ids)} vs {token_emb.shape[0]}"
            )

            word_arr = self.pooling.token_to_word(
                token_emb, word_ids, hidden_size=self.dimensions
            )
            word_embeddings_per_doc.append(word_arr)

        return DechunkedResult(
            token_embeddings=token_embeddings_per_doc,
            word_embeddings=word_embeddings_per_doc,
            cls_embeddings=cls_tokens_per_doc,
        )

# @decorators.singleton
# class Embedder:
#     def __init__(
#         self,
#         max_length: Optional[int] = None,
#         stride: Optional[int] = None,
#         device: Optional[str] = None,
#     ):
#         self.tokenizer = AutoTokenizer.from_pretrained(config.EMBEDDING_MODEL)
#         self.model = AutoModel.from_pretrained(
#             config.EMBEDDING_MODEL,
#             trust_remote_code=True,
#             torch_dtype=torch.float16,
#         )
#         for p in self.model.parameters():
#             p.requires_grad = False
#         self.dimensions = self.model.config.hidden_size
#         self.max_length = max_length or self.tokenizer.model_max_length
#         self.stride = stride or min(32, math.floor(self.max_length / 3))
#         self.device = device or config.DEVICE
#         self.model.to(self.device)
#         self.cls_detector = ClsDetector(self.tokenizer, self.model)
#
#     def chunk(
#         self,
#         texts: Union[List[str], List[List[str]]],
#         is_split_into_words: bool = False,
#     ) -> ChunkResult:
#         encodings = self.tokenizer(
#             texts,
#             truncation=False,
#             padding=False,
#             return_offsets_mapping=False,
#             return_attention_mask=True,
#             is_split_into_words=is_split_into_words,
#         )
#         all_chunks: List[Chunk] = []
#         token_word_mapping: List[SentenceTokenMapping] = []
#
#         if isinstance(encodings["input_ids"][0], int):
#             encodings["input_ids"] = [encodings["input_ids"]]
#             encodings["attention_mask"] = [encodings["attention_mask"]]
#
#         for sentence_index in range(len(encodings["input_ids"])):
#             input_ids = encodings["input_ids"][sentence_index]
#             attn = encodings["attention_mask"][sentence_index]
#
#             word_ids_for_encoding = None
#             if hasattr(encodings, "encodings"):
#                 word_ids_for_encoding = encodings.encodings[
#                     sentence_index
#                 ].word_ids
#             else:
#                 single = self.tokenizer(
#                     texts[sentence_index],
#                     is_split_into_words=is_split_into_words,
#                     return_offsets_mapping=False,
#                     return_attention_mask=False,
#                     truncation=False,
#                     padding=False,
#                 )
#                 if hasattr(single, "encodings"):
#                     word_ids_for_encoding = single.encodings[0].word_ids
#
#             if word_ids_for_encoding is None:
#                 raise Exception("Unable to obtain word_ids from tokenizer")
#
#             token_word_mapping.append(
#                 SentenceTokenMapping(
#                     token_count=len(input_ids),
#                     word_ids=list(word_ids_for_encoding),
#                 )
#             )
#
#             # chunk the tokenizer tokens (these are tokenizer token indices)
#             start = 0
#             while start < len(input_ids):
#                 end = min(start + self.max_length, len(input_ids))
#                 all_chunks.append(
#                     Chunk(
#                         input_ids=input_ids[start:end],
#                         attention_mask=attn[start:end],
#                         sentence_index=sentence_index,
#                         word_ids=word_ids_for_encoding[start:end],
#                         start=start,
#                         end=end,
#                     )
#                 )
#                 if end == len(input_ids):
#                     break
#                 start = end - self.stride if self.stride > 0 else end
#
#         return ChunkResult(
#             chunks=all_chunks,
#             mapping=token_word_mapping,
#         )
#
#     def dechunk(
#         self,
#         chunk_result: ChunkResult,
#         model_outputs: List[NDArray[np.floating]],
#         cls_embeddings: List[NDArray[np.floating]],
#         agg: str = "weighted",
#     ) -> DechunkedResult:
#         if len(model_outputs) == 0:
#             return DechunkedResult([], [], [])
#
#         # Convert batches back into documents/sentences and their tokens
#         combined: Dict[int, Dict[int, List[NDArray[np.floating]]]] = defaultdict(
#             lambda: defaultdict(list)
#         )
#         stride = self.stride
#
#         cls_tokens: Dict[int, List[NDArray[np.floating]]] = defaultdict(list)
#
#         for meta, output, cls_emb in zip(chunk_result.chunks, model_outputs, cls_embeddings):
#             b_idx = meta.sentence_index
#             chunk_len = len(meta.input_ids)
#             start_pos = meta.start
#             end_pos = meta.end
#             cls_tokens[b_idx].append(cls_emb)
#
#             for i, emb in enumerate(output):
#                 pos = start_pos + i
#                 weight = 1.0
#                 if agg == "weighted":
#                     if start_pos > 0 and i < stride:
#                         weight = 0.5 + 0.5 * (i / stride)
#                     elif end_pos < chunk_result.mapping[b_idx].token_count and i >= chunk_len - stride:
#                         dist_from_end = (chunk_len - 1) - i
#                         weight = 0.5 + 0.5 * (dist_from_end / stride)
#                 combined[b_idx][pos].append((emb, weight))  # type: ignore
#
#         cls_tokens_per_doc = [None] * len(cls_tokens)
#         for doc_idx, tokens in cls_tokens.items():
#             cls_tokens_per_doc[doc_idx] = normalize(np.mean(tokens, axis=0))  # type:ignore
#
#         token_embeddings_per_doc: List[np.ndarray] = []
#         orig_token_maps: List[List[int]] = []
#
#         for doc_idx in range(len(chunk_result.mapping)):
#             if doc_idx not in combined:
#                 # For some reason we don't have tokens,
#                 # so create a zero array and continue
#                 token_embeddings_per_doc.append(
#                     np.zeros((0, model_outputs[0].shape[-1]))
#                 )
#                 orig_token_maps.append([])
#                 continue
#
#             positions = sorted(combined[doc_idx].keys())
#             if not model_outputs:
#                 hidden_size = self.dimensions
#             else:
#                 hidden_size = combined[doc_idx][positions[0]][0][0].shape[-1]
#
#             num_tokens = chunk_result.mapping[doc_idx].token_count
#             merged = np.zeros((num_tokens, hidden_size))
#
#             for pos in positions:
#                 emb_weight_list = combined[doc_idx][pos]
#
#                 # Can have multiple tokens when we have stride
#                 if len(emb_weight_list) == 1:
#                     merged[pos] = emb_weight_list[0][0]
#
#                 elif agg == "mean":
#                     emb_list = [e_w[0] for e_w in emb_weight_list]
#                     merged[pos] = np.mean(emb_list, axis=0)
#
#                 elif agg == "first":
#                     merged[pos] = emb_weight_list[0][0]
#
#                 elif agg == "weighted":
#                     embeddings = np.stack([e_w[0] for e_w in emb_weight_list], axis=0)
#                     weights = np.array([e_w[1] for e_w in emb_weight_list])[:, np.newaxis]
#
#                     weighted_sum = np.sum(embeddings * weights, axis=0)
#                     sum_of_weights = float(np.sum(weights))
#
#                     if sum_of_weights > 0:
#                         merged[pos] = weighted_sum / sum_of_weights
#                     else:
#                         merged[pos] = embeddings[0]
#
#                 else:
#                     raise ValueError("agg must be 'mean' or 'first'")
#
#             token_embeddings_per_doc.append(merged.astype(np.float16))
#             orig_token_maps.append(list(chunk_result.mapping[doc_idx].word_ids))
#
#         # Aggregate the token embeddings to word embeddings
#         word_embeddings_per_doc: List[np.ndarray] = []
#         for doc_idx, token_emb in enumerate(token_embeddings_per_doc):
#             word_ids = orig_token_maps[doc_idx]
#             if len(word_ids) == 0:
#                 word_embeddings_per_doc.append(np.zeros(token_emb.shape[-1]))
#                 logger.warning("No word ids found during dechunking")
#                 continue
#
#             # find a number of words (max word_id + 1 ignoring None)
#             valid_word_ids = [w for w in word_ids if w is not None]
#             if len(valid_word_ids) == 0:
#                 word_embeddings_per_doc.append(np.zeros(token_emb.shape[-1]))
#                 logger.warning("No valid word ids found during dechunking")
#                 continue
#
#             num_words = max(valid_word_ids) + 1
#             # collect token embeddings per word
#             accumulator: List[List[np.ndarray]] = [[] for _ in range(num_words)]
#             for tok_idx, w_id in enumerate(word_ids):
#                 if w_id is None:
#                     continue
#                 accumulator[w_id].append(token_emb[tok_idx])
#
#             # aggregate per word
#             word_arr = np.zeros((num_words, token_emb.shape[-1]))
#             for w in range(num_words):
#                 if len(accumulator[w]) == 0:
#                     word_arr[w] = np.zeros(token_emb.shape[-1])  # or nan
#                 else:
#                     word_arr[w] = np.mean(
#                         np.stack(accumulator[w], axis=0), axis=0
#                     )
#             word_embeddings_per_doc.append(word_arr.astype(np.float16))
#
#         return DechunkedResult(
#             token_embeddings=token_embeddings_per_doc,
#             word_embeddings=word_embeddings_per_doc,
#             cls_embeddings=cls_tokens_per_doc,  # type: ignore
#         )
#
#     def encode(
#         self,
#         chunk_result: ChunkResult,
#         batch_size: Optional[int] = None,
#         agg: str = "mean",
#     ) -> EmbeddingResult:
#         chunks = chunk_result.chunks
#         model_outputs: List[NDArray[np.floating]] = []
#         batch_size = batch_size or config.INFERENCE_BATCH_SIZE
#         cls_tokens = []
#
#         # forward in minibatches of chunks
#         for i in range(0, len(chunks), batch_size):
#             batch = chunks[i: i + batch_size]
#             batch_inputs = self.tokenizer.pad(
#                 {
#                     "input_ids": [c.input_ids for c in batch],
#                     "attention_mask": [c.attention_mask for c in batch],
#                 },
#                 return_tensors="pt",
#             ).to(self.device)
#
#             with torch.no_grad():
#                 outputs = self.model(**batch_inputs, output_hidden_states=True)
#
#             cls_emb = self.cls_detector.get_cls_embedding(batch_inputs, outputs.last_hidden_state.cpu().numpy())
#             cls_tokens.extend(cls_emb.tolist())
#
#             n_take = min(4, len(outputs.hidden_states))
#             last_hidden = (
#                 torch.mean(torch.stack(outputs.hidden_states[-n_take:]), dim=0)
#                 .cpu()
#                 .numpy()
#                 .astype(np.float16)
#             )
#
#             lengths = [len(c.input_ids) for c in batch]
#             for j, length in enumerate(lengths):
#                 model_outputs.append(np.nan_to_num(last_hidden[j, :length, :]).astype(np.float16))
#
#         dechunked = self.dechunk(
#             chunk_result=chunk_result,
#             model_outputs=model_outputs,
#             cls_embeddings=cls_tokens,
#             agg=agg,
#         )
#
#         return EmbeddingResult(
#             token_embeddings=dechunked.token_embeddings,
#             word_embeddings=[normalize(e) for e in dechunked.word_embeddings],
#             sentence_embeddings=dechunked.cls_embeddings,
#             mapping=chunk_result.mapping,
#         )
#
#     def __call__(
#         self,
#         texts: Union[List[str], List[List[str]]],
#         is_split_into_words: bool = False,
#         agg: str = "weighted",
#         batch_size: Optional[int] = None,
#     ) -> EmbeddingResult:
#         chunk_result = self.chunk(
#             texts,
#             is_split_into_words=is_split_into_words
#         )
#         return self.encode(
#             chunk_result=chunk_result,
#             batch_size=batch_size,
#             agg=agg
#         )
