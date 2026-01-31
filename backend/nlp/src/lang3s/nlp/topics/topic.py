import traceback
from typing import TYPE_CHECKING, Optional, Sequence

from lang3s import config
from lang3s.nlp.topics.reducer import OnlineReducer
from lang3s.nlp.topics.shared_types import TopicSentence

if TYPE_CHECKING:
    pass

import numpy as np
import sqlalchemy
from numpy.typing import NDArray
from sqlalchemy import Boolean, cast, distinct, not_, select

from lang3s.data.db import Database
from lang3s.data.db.models import TextAnnotationsTable
from lang3s.utils.maths import normalize, weighted_average


class Topic:
    def __init__(
        self,
        id: str,
        support: int,
        embedding: NDArray[np.floating],
        pca_centroid: NDArray[np.floating],
        reducer: OnlineReducer,
        min_sim_threshold: float,
        is_fixed: bool = False,
        name: Optional[str] = None,
        doc_support: int = 0,
    ) -> None:
        self.id = id
        if isinstance(id, Topic):
            traceback.print_stack()
        self.support = support
        self.doc_support = doc_support
        self.centroid: NDArray[np.floating] = pca_centroid
        self.embedding: NDArray[np.floating] = embedding
        self.reducer = reducer
        self.min_sim_threshold = min_sim_threshold
        self.is_fixed = is_fixed
        self.name = name if name is not None else id
        self.doc_ids = set()

    @property
    def doc_count(self) -> int:
        return self.doc_support + len(self.doc_ids)

    @property
    def sentence_count(self) -> int:
        db = Database()
        with db.session() as session:  # type: Session
            stmt = select(
                sqlalchemy.func.count(distinct(TextAnnotationsTable.id))
            ).where(
                TextAnnotationsTable.type_ == "sentence",
                (1 - TextAnnotationsTable.embedding.cosine_distance(self.embedding))
                >= config.FULL_EMBEDDING_THRESHOLD,
                cast(TextAnnotationsTable.metadata_["is_stopword"], Boolean) == False,
            )
            return session.scalar(stmt)

    def merge(self, other: "Topic"):
        self.centroid = normalize(
            weighted_average(
                (self.centroid, self.support), (other.centroid, other.support)
            )
        )
        self.doc_ids.update(other.doc_ids)
        self.embedding = normalize(
            weighted_average(
                (self.embedding, self.support),
                (other.embedding, other.support),
            )
        )
        self.support += other.support

    def copy(self) -> "Topic":
        return Topic(
            id=self.id,
            support=self.support,
            embedding=self.embedding.copy(),
            pca_centroid=self.centroid.copy(),
            is_fixed=self.is_fixed,
            reducer=self.reducer,
            min_sim_threshold=self.min_sim_threshold,
        )

    def get_sentences(self, limit: int = 1000):
        db = Database()
        with db.session() as session:  # type: Session
            similarity_score = 1 - TextAnnotationsTable.embedding.cosine_distance(
                self.embedding
            )
            stmt = (
                select(
                    TextAnnotationsTable.documentId,
                    TextAnnotationsTable.sentenceId,
                    TextAnnotationsTable.textId,
                    TextAnnotationsTable.content,
                    TextAnnotationsTable.embedding,
                    TextAnnotationsTable.cleaned,
                    similarity_score.label("cosine_similarity"),
                )
                .where(
                    TextAnnotationsTable.type_ == "sentence",
                    similarity_score >= config.FULL_EMBEDDING_THRESHOLD,
                    not_(cast(TextAnnotationsTable.metadata_["is_stopword"], Boolean)),
                )
                .order_by(similarity_score.desc())
                .limit(limit)
            )
            sentences: Sequence[SearchResult] = session.execute(stmt).all()  # type:ignore
            return [
                TopicSentence(
                    text=row.content,
                    clean=row.cleaned,
                    doc_id=row.documentId,
                    text_id=row.textId,
                    sentence_id=row.sentenceId,
                    similarity=row.cosine_similarity,
                )
                for (row) in sentences
            ]
