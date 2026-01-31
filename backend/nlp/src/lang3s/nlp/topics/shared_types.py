from typing import NamedTuple

from pgvector import HalfVector


class SearchResult(NamedTuple):
    documentId: str
    sentenceId: int
    textId: str
    content: str
    embedding: HalfVector
    cleaned: str
    cosine_similarity: float


class TopicSentence(NamedTuple):
    doc_id: str
    text_id: str
    sentence_id: int
    text: str
    clean: str
    similarity: float
