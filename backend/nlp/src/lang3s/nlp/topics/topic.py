import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, Sequence

import numpy as np
import sqlalchemy
from numpy.typing import NDArray
from sqlalchemy import Boolean, cast, distinct, func, not_, select, text

import lang3s.data.db.database as db
from lang3s import config
from lang3s.data.db.models import TextAnnotationsTable
from lang3s.nlp.topics.reducer import OnlineReducer
from lang3s.nlp.topics.shared_types import SearchResult, TopicSentence
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
        last_updated: Optional[datetime] = None,
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
        self.last_updated = last_updated

    @property
    def doc_count(self) -> int:
        return self.doc_support + len(self.doc_ids)

    @property
    def sentence_count(self) -> int:
        with db.get_session() as session:
            stmt = select(
                sqlalchemy.func.count(distinct(TextAnnotationsTable.id))
            ).where(
                TextAnnotationsTable.type_ == "sentence"
                and (1 - TextAnnotationsTable.embedding.cosine_distance(self.embedding))
                >= config.FULL_EMBEDDING_THRESHOLD
                and cast(TextAnnotationsTable.metadata_["is_stopword"], Boolean)
                == False,
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
        self.last_updated = datetime.now()

    def copy(self) -> "Topic":
        return Topic(
            id=self.id,
            support=self.support,
            embedding=self.embedding.copy(),
            pca_centroid=self.centroid.copy(),
            is_fixed=self.is_fixed,
            reducer=self.reducer,
            min_sim_threshold=self.min_sim_threshold,
            last_updated=self.last_updated,
        )

    def get_sentences(
        self, limit: int = 1000, randomize: bool = False
    ) -> list[TopicSentence]:
        with db.get_session() as session:
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
                .order_by(func.random() if randomize else similarity_score.desc())
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


class TopicList:
    def __init__(self) -> None:
        self._topics: list[Topic] = []
        self._next_topic_id = 0

    def __iter__(self):
        return iter(self._topics)

    def __len__(self):
        return len(self._topics)

    def __getitem__(self, index: int) -> Topic:
        return self._topics[index]

    def __repr__(self) -> str:
        return repr(self._topics)

    def __contains__(self, topic_id: int) -> bool:
        return topic_id in self._topics

    def __str__(self) -> str:
        return str(self._topics)

    def clear(self) -> None:
        self._topics.clear()
        self._next_topic_id = 0

    def index_of(self, topic_id: int) -> int:
        for i, topic in enumerate(self._topics):
            if topic.id == topic_id:
                return i
        raise -1

    def renormalize_topic_embeddings(self, reducer: OnlineReducer) -> None:
        new_reduced_centroids = reducer.transform(
            np.vstack([topic.embedding for topic in self._topics])
        )
        for topic, reduced_centroid in zip(self._topics, new_reduced_centroids):
            topic.centroid = normalize(reduced_centroid.squeeze())

    def create_new_topic(
        self,
        embedding: NDArray[np.floating],
        pca_centroid: NDArray[np.floating],
        reducer: OnlineReducer,
        min_sim_threshold: float,
        document_id: str,
    ) -> Topic:
        topic = Topic(
            id=f"topic-{self._next_topic_id}",
            support=1,
            embedding=embedding,
            pca_centroid=pca_centroid,
            is_fixed=False,
            reducer=reducer,
            min_sim_threshold=min_sim_threshold,
            last_updated=datetime.now(),
        )
        topic.doc_ids.add(document_id)
        self._next_topic_id += 1
        self._topics.append(topic)
        return topic

    def add_topic(self, topic: Topic) -> None:
        self._topics.append(topic)
        if type(topic.id) is int:
            self._next_topic_id = max(self._next_topic_id, topic.id)

    def update_sentence_counts(self):
        with ThreadPoolExecutor(max_workers=20) as executor:
            sentence_counts = list(
                executor.map(_get_topic_count, [t.embedding for t in self._topics])
            )
            for i, sc in enumerate(sentence_counts):
                self._topics[i].support = i

    def update_topics(self, new_topics: list[Topic]) -> None:
        self._topics = new_topics


def _get_topic_count(embedding: np.ndarray):
    with db.get_session() as session:
        session.execute(text("SET jit = off;"))
        session.execute(text("SET hnsw.ef_search = 100;"))
        stmt = select(func.count()).select_from(
            select(TextAnnotationsTable.id)
            .where(
                TextAnnotationsTable.type_ == "sentence",
                cast(TextAnnotationsTable.metadata_["is_stopword"], Boolean).is_(False),
                TextAnnotationsTable.embedding.cosine_distance(embedding) < 0.35,
            )
            .order_by(TextAnnotationsTable.embedding.cosine_distance(embedding))
            .limit(25000)
            .subquery()
        )
        return session.scalar(stmt)
