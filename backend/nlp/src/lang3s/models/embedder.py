import math
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List

import numpy as np
import torch
from numpy.typing import NDArray

import lang3s.config as config
from lang3s.maths import normalize

if TYPE_CHECKING:
    pass

from logging import Logger
from typing import Optional, Union

from transformers import AutoModel, AutoTokenizer  # pyright: ignore[reportPrivateImportUsage]

from lang3s.utils import decorators

from .types import (
    Chunk,
    ChunkResult,
    DechunkedResult,
    EmbeddingResult,
    SentenceTokenMapping,
)

logger = Logger(__name__)


@decorators.singleton
class Embedder:
    def __init__(
        self,
        max_length: Optional[int] = None,
        stride: Optional[int] = None,
        device: Optional[str] = None,
    ):
        self.tokenizer = AutoTokenizer.from_pretrained(config.EMBEDDING_MODEL)
        self.model = AutoModel.from_pretrained(
            config.EMBEDDING_MODEL,
            trust_remote_code=True,
            torch_dtype=torch.float16,
        )
        for p in self.model.parameters():
            p.requires_grad = False
        self.dimensions = self.model.config.hidden_size
        self.max_length = max_length or self.tokenizer.model_max_length
        self.stride = stride or min(32, math.floor(self.max_length / 3))
        self.device = device or config.DEVICE
        self.model.to(self.device)

    def chunk(
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

        for sentence_index in range(len(encodings["input_ids"])):
            input_ids = encodings["input_ids"][sentence_index]
            attn = encodings["attention_mask"][sentence_index]

            word_ids_for_encoding = None
            if hasattr(encodings, "encodings"):
                word_ids_for_encoding = encodings.encodings[
                    sentence_index
                ].word_ids
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
                raise Exception("Unable to obtain word_ids from tokenizer")

            token_word_mapping.append(
                SentenceTokenMapping(
                    token_count=len(input_ids),
                    word_ids=list(word_ids_for_encoding),
                )
            )

            # chunk the tokenizer tokens (these are tokenizer token indices)
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

        return ChunkResult(
            chunks=all_chunks,
            mapping=token_word_mapping,
        )

    def dechunk(
        self,
        chunk_result: ChunkResult,
        model_outputs: List[NDArray[np.floating]],
        agg: str = "mean",
    ) -> DechunkedResult:
        if len(model_outputs) == 0:
            return DechunkedResult([], [])

        # Convert batches back into documents/sentences and their tokens
        combined: Dict[int, Dict[int, List[NDArray[np.floating]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for meta, output in zip(chunk_result.chunks, model_outputs):
            b_idx = meta.sentence_index
            start = meta.start
            for i, emb in enumerate(output):
                pos = start + i
                combined[b_idx][pos].append(
                    emb)  # type: ignore

        token_embeddings_per_doc: List[np.ndarray] = []
        orig_token_maps: List[List[int]] = []

        for doc_idx in range(len(chunk_result.mapping)):
            if doc_idx not in combined:
                # For some reason we don't have tokens,
                # so create a zero array and continue
                token_embeddings_per_doc.append(
                    np.zeros((0, model_outputs[0].shape[-1]))
                )
                orig_token_maps.append([])
                continue

            positions = sorted(combined[doc_idx].keys())
            hidden_size = combined[doc_idx][positions[0]][0].shape[-1]

            # create array of size num_tokens (based on orig_map token_count)
            num_tokens = chunk_result.mapping[doc_idx].token_count
            merged = np.zeros((num_tokens, hidden_size))
            for pos in positions:
                emb_list = combined[doc_idx][pos]
                # Can have multiple tokens when we have stride
                if len(emb_list) == 1:
                    merged[pos] = emb_list[0]
                elif agg == "mean":
                    merged[pos] = np.mean(emb_list, axis=0)
                elif agg == "first":
                    merged[pos] = emb_list[0]
                else:
                    raise ValueError("agg must be 'mean' or 'first'")

            token_embeddings_per_doc.append(merged.astype(np.float16))
            orig_token_maps.append(list(chunk_result.mapping[doc_idx].word_ids))

        # Aggregate the token embeddings to word embeddings
        word_embeddings_per_doc: List[np.ndarray] = []
        for doc_idx, token_emb in enumerate(token_embeddings_per_doc):
            word_ids = orig_token_maps[doc_idx]
            if len(word_ids) == 0:
                word_embeddings_per_doc.append(np.zeros(token_emb.shape[-1]))
                logger.warning("No word ids found during dechunking")
                continue

            # find number of words (max word_id + 1 ignoring None)
            valid_word_ids = [w for w in word_ids if w is not None]
            if len(valid_word_ids) == 0:
                word_embeddings_per_doc.append(np.zeros(token_emb.shape[-1]))
                logger.warning("No valid word ids found during dechunking")
                continue

            num_words = max(valid_word_ids) + 1
            # collect token embeddings per word
            accumulator: List[List[np.ndarray]] = [[] for _ in range(num_words)]
            for tok_idx, w_id in enumerate(word_ids):
                if w_id is None:
                    continue
                accumulator[w_id].append(token_emb[tok_idx])

            # aggregate per word
            word_arr = np.zeros((num_words, token_emb.shape[-1]))
            for w in range(num_words):
                if len(accumulator[w]) == 0:
                    word_arr[w] = np.zeros(token_emb.shape[-1])  # or nan
                else:
                    word_arr[w] = np.mean(
                        np.stack(accumulator[w], axis=0), axis=0
                    )
            word_embeddings_per_doc.append(word_arr.astype(np.float16))

        return DechunkedResult(
            token_embeddings=token_embeddings_per_doc,
            word_embeddings=word_embeddings_per_doc,
        )

    def encode(
        self,
        chunk_result: ChunkResult,
        batch_size: Optional[int] = None,
        agg: str = "mean",
    ) -> EmbeddingResult:
        chunks = chunk_result.chunks
        model_outputs: List[NDArray[np.floating]] = []
        batch_size = batch_size or config.INFERENCE_BATCH_SIZE

        # forward in minibatches of chunks
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i: i + batch_size]
            batch_inputs = self.tokenizer.pad(
                {
                    "input_ids": [c.input_ids for c in batch],
                    "attention_mask": [c.attention_mask for c in batch],
                },
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**batch_inputs, output_hidden_states=True)

            n_take = min(4, len(outputs.hidden_states))
            last_hidden = (
                torch.mean(torch.stack(outputs.hidden_states[-n_take:]), dim=0)
                .cpu()
                .numpy()
                .astype(np.float16)
            )

            lengths = [len(c.input_ids) for c in batch]
            for j, length in enumerate(lengths):
                model_outputs.append(last_hidden[j, :length, :])

        dechunked = self.dechunk(
            chunk_result,
            model_outputs,
            agg=agg,
        )

        sentence_embeddings = []
        for emb in dechunked.token_embeddings:
            sentence_embeddings.append(
                normalize(emb.mean(axis=0)).astype(np.float16)
            )
        return EmbeddingResult(
            token_embeddings=dechunked.token_embeddings,
            word_embeddings=[normalize(e) for e in dechunked.word_embeddings],
            sentence_embeddings=sentence_embeddings,
            mapping=chunk_result.mapping,
        )

    def __call__(
        self,
        texts: Union[List[str], List[List[str]]],
        is_split_into_words: bool = False,
        agg: str = "mean",
        batch_size: Optional[int] = None,
    ) -> EmbeddingResult:
        chunk_result = self.chunk(
            texts, is_split_into_words=is_split_into_words
        )
        return self.encode(
            chunk_result=chunk_result, batch_size=batch_size, agg=agg
        )

    # def embed_doc(self, doc: "Document"):
    #     if doc.text is None:
    #         return

    #     sentences = [[t.text for t in s.tokens] for s in doc.text.sentences]
    #     result = self.__call__(sentences, is_split_into_words=True)

    #     doc_emb = np.zeros(
    #         result.sentence_embeddings[0].shape[-1], dtype=np.float16
    #     )

    #     for sentence, word_embeddings, sentence_embedding in zip(
    #         doc.text.sentences,
    #         result.word_embeddings,
    #         result.sentence_embeddings,
    #     ):
    #         sentence.embedding = sentence_embedding
    #         weight = sentence.metadata[Metadata.WEIGHT.value]
    #         if weight > 0:
    #             doc_emb += sentence_embedding * float(weight)

    #         # Assign the token embeddings
    #         for token, emb in zip(sentence.tokens, word_embeddings):
    #             token.embedding = emb

    #     # Document level embedding is the weighted sum of the
    #     # sentence embeddings
    #     doc.text.embedding = normalize(doc_emb).astype(np.float16)

    #     for annotation in doc.text.annotations:
    #         annotation.embedding = (
    #             np.array([t.embedding for t in annotation.tokens])
    #             .mean(axis=0)
    #             .astype(np.float16)
    #         )
    #         if np.any(np.isnan(annotation.embedding)):
    #             logger.error(
    #                 f"Error: NaN value in embedding for {annotation.text} {[t.text for t in annotation.tokens]} "
    #             )
    #             annotation.embedding = np.nan_to_num(annotation.embedding)
