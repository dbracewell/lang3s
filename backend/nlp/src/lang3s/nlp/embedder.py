from typing import TYPE_CHECKING, List, cast

import numpy as np
import torch
from numpy.typing import NDArray
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer

import lang3s.config as config
from lang3s.types import Text

if TYPE_CHECKING:
    from lang3s.types import Document


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
                config.EMBEDDING_MODEL,
                trust_remote_code=True,
                device=config.DEVICE,
            )
            self._tokenizer = self.model.tokenizer
            self._max_tokens = self._tokenizer.model_max_length - 12
            self._dimension = self.model.get_sentence_embedding_dimension()

    @property
    def dimensions(self):
        return self._dimension

    def __call__(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts).tolist()

    def _embed(self, texts: List[str]) -> NDArray[np.float32]:
        tokens = [t.split() for t in texts]
        if len(tokens) == 0:
            return np.array(self._dimension, dtype=np.float32)
        max_token_count = max([len(t.split()) for t in texts])

        if max_token_count > self._max_tokens:
            return self._batch_embed(texts)

        return cast(
            NDArray[np.float32],
            self.model.encode(
                texts,
                device=config.DEVICE,
                normalize_embeddings=True,
                convert_to_numpy=True,
            ),
        )

    def _batch_embed(self, texts: List[str]) -> NDArray[np.float32]:
        docs = [t.split() for t in texts]
        chunked = _chunk_documents(
            docs, chunk_size=self._max_tokens, overlap=10
        )

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
        _weight_sentences(doc.text, embeddings)
        for sentence, s_embedding in zip(doc.text.sentences, embeddings):
            sentence.embedding = s_embedding
        annotation_texts = [a.text for a in doc.text.annotations]
        embeddings = self._embed(annotation_texts)
        for annotation, embedding in zip(doc.text.annotations, embeddings):
            annotation.embedding = embedding


def _weight_sentences(text: Text, embeddings: NDArray[np.float32]):
    texts = []
    embs = []
    idxs = []
    for idx, (s, e) in enumerate(zip(text.sentences, embeddings)):
        if not s.is_stopword:
            texts.append(s.to_string(True, True, True))
            embs.append(e)
            idxs.append(idx)

    if len(embs) == 0:
        text.embedding = embeddings.mean(axis=0)
        for s in text.sentences:
            s.metadata["weight"] = 1 / len(text.sentences)

    elif len(embs) == 1:
        text.embedding = embs[0].copy()
        text.sentences[idxs[0]].metadata["weight"] = 1

    else:
        sentence_weights = (
            TfidfVectorizer().fit_transform(texts).mean(axis=1).A1  # type: ignore
        )
        sentence_weights = sentence_weights / sentence_weights.sum()
        text.embedding = np.average(embs, axis=0, weights=sentence_weights)
        for idx, weight in zip(idxs, sentence_weights):
            text.sentences[idx].metadata["weight"] = weight
