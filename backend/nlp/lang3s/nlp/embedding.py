from typing import TYPE_CHECKING, List

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from lang3s import config

if TYPE_CHECKING:
    from lang3s.core import Document


def _chunk_tokens(tokens, chunk_size, overlap=10):
    start = 0
    while start < len(tokens):
        end = start + chunk_size
        yield start, tokens[start:end]
        start += chunk_size - overlap


def _chunk_documents(docs, chunk_size, overlap=10):
    chunked = []
    for i, tokens in enumerate(docs):
        for start, chunk in _chunk_tokens(tokens, chunk_size, overlap):
            chunked.append((i, start, chunk))
    return chunked


class Embedder:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "initialized"):
            self.initialized = True
            self.model = SentenceTransformer(
                config.EMBEDDING_MODEL, trust_remote_code=True
            )
            self._tokenizer = self.model.tokenizer
            self._max_tokens = self._tokenizer.model_max_length - 12
            self._dimension = self.model.get_sentence_embedding_dimension()

    @property
    def dimensions(self):
        return self._dimension

    def __call__(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts).tolist()

    def _embed(self, texts: List[str]) -> np.ndarray:
        max_token_count = max([len(t.split()) for t in texts])

        if max_token_count > self._max_tokens:
            return self._batch_embed(texts)

        return self.model.encode(
            texts,
            device=config.DEVICE,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

    def _batch_embed(self, texts: List[str]) -> np.ndarray:
        docs = [t.split() for t in texts]
        chunked = _chunk_documents(docs, chunk_size=self._max_tokens, overlap=10)

        all_embeddings: List[torch.Tensor] = [
            torch.zeros(self._dimension).to(config.DEVICE)  # pyright: ignore[reportArgumentType] # type: ignore
            for i in range(len(texts))
        ]
        all_counts: List[torch.Tensor] = [
            torch.zeros(1).to(config.DEVICE) for i in range(len(texts))
        ]

        for i in range(0, len(chunked), config.INFERENCE_BATCH_SIZE):
            batch = chunked[i : i + config.INFERENCE_BATCH_SIZE]
            batch_tokens = [" ".join(tokens) for (_, _, tokens) in batch]

            with torch.inference_mode():
                outputs = self.model.encode(
                    batch_tokens,
                    device=config.DEVICE,
                    convert_to_tensor=True,
                    normalize_embeddings=True,
                )

            for (doc_id, _, _), emb in zip(batch, outputs):
                all_embeddings[doc_id] += emb
                all_counts[doc_id] += 1

        final_embeddings = []
        for emb, count in zip(all_embeddings, all_counts):
            count = count.unsqueeze(-1).clamp(min=1.0)  # avoid divide-by-zero
            final_embeddings.append((emb / count).cpu().numpy().squeeze())

        return np.array(final_embeddings)

    def embed_doc(self, doc: "Document"):
        if doc.text is None:
            return
        sentences = [s.text for s in doc.text.sentences]
        embeddings = self._embed(sentences)

        doc.text.embedding = embeddings.mean(axis=0).tolist()
        for sentence, s_embedding in zip(doc.text.sentences, embeddings):
            sentence.embedding = s_embedding.tolist()

        annotation_texts = [a.text for a in doc.text.annotations]
        embeddings = self._embed(annotation_texts)
        for annotation, embedding in zip(doc.text.annotations, embeddings):
            annotation.embedding = embedding.tolist()
