import datetime
import logging
import os
import time
import traceback
from typing import Iterable, List, NamedTuple, Optional, Sequence

import joblib
import numpy as np
import shortuuid
import sqlalchemy
from numpy.typing import NDArray
from pgvector import HalfVector
from sklearn.decomposition import IncrementalPCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import Boolean, Select, cast, delete, distinct, not_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from lang3s import config
from lang3s.db import Database
from lang3s.db.models import TextAnnotationsTable, TopicsTable
from lang3s.maths import cosine, normalize, weighted_average
from lang3s.shared_types import Document
from lang3s.utils import flatten
from lang3s.utils.meta import SingletonMeta

logger = logging.getLogger("TopicModel")


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


REDUCED_DIMENSIONS = 200
FULL_EMBEDDING_THRESHOLD = 0.65


class OnlineReducer:
    def __init__(self):
        self.pca = IncrementalPCA(n_components=REDUCED_DIMENSIONS)
        self.fitted = False

    def fit_batch(self, batch):
        self.pca.partial_fit(batch)
        self.fitted = True

    def transform(self, vectors):
        if not self.fitted:
            raise RuntimeError("PCA not fitted yet.")
        return self.pca.transform(vectors).astype(np.float32)

    def save(self):
        output_file = os.path.join(config.MODELS_DIR, "online_reducer.pkl")
        joblib.dump(self.pca, output_file)

    @staticmethod
    def load():
        model_file = os.path.join(config.MODELS_DIR, "online_reducer.pkl")
        reducer = OnlineReducer()
        if os.path.exists(model_file):
            reducer.pca = joblib.load(model_file)
            reducer.fitted = True
        return reducer


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
    ) -> None:
        self.id = id
        self.support = support
        self.centroid: NDArray[np.floating] = pca_centroid
        self.embedding: NDArray[np.floating] = embedding
        self.reducer = reducer
        self.min_sim_threshold = min_sim_threshold
        self.is_fixed = is_fixed
        self.name = name if name is not None else id

    @property
    def doc_count(self) -> int:
        db = Database()
        with db.session() as session:  # type: Session
            stmt = select(
                sqlalchemy.func.count(distinct(TextAnnotationsTable.documentId))
            ).where(
                TextAnnotationsTable.type_ == "sentence",
                (1 - TextAnnotationsTable.embedding.cosine_distance(self.embedding))
                >= FULL_EMBEDDING_THRESHOLD,
                cast(TextAnnotationsTable.metadata_["is_stopword"], Boolean) == False,
            )
            return session.scalar(stmt)

    @property
    def sentence_count(self) -> int:
        db = Database()
        with db.session() as session:  # type: Session
            stmt = select(
                sqlalchemy.func.count(distinct(TextAnnotationsTable.id))
            ).where(
                TextAnnotationsTable.type_ == "sentence",
                (1 - TextAnnotationsTable.embedding.cosine_distance(self.embedding))
                >= FULL_EMBEDDING_THRESHOLD,
                cast(TextAnnotationsTable.metadata_["is_stopword"], Boolean) == False,
            )
            return session.scalar(stmt)

    def merge(self, other: "Topic"):
        self.centroid = normalize(
            weighted_average(
                (self.centroid, self.support), (other.centroid, other.support)
            )
        )
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
                    similarity_score >= FULL_EMBEDDING_THRESHOLD,
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


DB_COLUMNS = [
    "id",
    "support",
    "embedding",
    "is_fixed",
    "name",
]


class Lang3sTopicModel(metaclass=SingletonMeta):
    def __init__(
        self,
    ):
        db = Database()
        self.sim_threshold: float = db.get_config_value(
            "topics_similarity_threshold", 0.45
        )
        self.fixed_sim_threshold: float = db.get_config_value(
            "topics_fixed_similarity_threshold", 0.6
        )
        self.merge_threshold: float = db.get_config_value(
            "topics_merge_threshold", 0.65
        )
        self.fixed_merge_threshold: float = db.get_config_value(
            "topics_fixed_merge_threshold", 0.75
        )
        self.min_support: int = db.get_config_value("topics_min_support", 10)
        self.min_document_count: int = db.get_config_value(
            "topics_min_document_count", 4
        )
        self.batch_size: int = db.get_config_value("topics_batch_size", 100)
        self.merge_frequency: int = db.get_config_value("topics_merge_frequency", 400)
        self.docs_added: int = 0
        self.sentences_added: int = 0
        self.total_time = 0
        self.buffer: List[NDArray[np.floating]] = []
        self.reducer = OnlineReducer.load()
        self._topics: List[Topic] = []
        self._load_topics()

    def _load_topics(self):
        self._topics = []
        db = Database()
        with db.session() as session:  # type: Session
            for topic in session.scalars(select(TopicsTable)).all():
                self._topics.append(
                    Topic(
                        id=topic.id,
                        support=topic.support,
                        embedding=topic.embedding.to_numpy(),
                        pca_centroid=np.zeros(REDUCED_DIMENSIONS),
                        is_fixed=topic.fixed,
                        name=topic.name,
                        reducer=self.reducer,
                        min_sim_threshold=self.sim_threshold,
                    )
                )
            if len(self._topics) == 0:
                return

            if not self.reducer.fitted:
                embeddings = []
                stmt: Select[tuple[TextAnnotationsTable]] = (
                    select(TextAnnotationsTable)
                    .where(
                        TextAnnotationsTable.type_ == "sentence",
                        cast(TextAnnotationsTable.metadata_["is_stopword"], Boolean)
                        == False,
                    )
                    .order_by(sqlalchemy.func.random())
                    .limit(5000)
                )
                for sentence in session.scalars(stmt).all():
                    embeddings.append(sentence.embedding.to_numpy())

                if len(embeddings) > REDUCED_DIMENSIONS:
                    self.reducer.fit_batch(embeddings)
                    self.__update_centroids()

    def partial_fit_sentence_embeddings(
        self, embeddings: List[List[float]] | List[NDArray[np.floating]]
    ):
        self.docs_added += 1
        self.sentences_added += len(embeddings)
        self.buffer.extend([normalize(np.array(e)) for e in embeddings])
        if self.docs_added % self.batch_size == 0:
            self.__run_batch()

    def partial_fit(self, docs: Iterable[Document]):
        for doc in docs:
            self.partial_fit_sentence_embeddings(
                [
                    s.embedding
                    for s in doc.text.sentences
                    if not s.is_stopword and s.embedding is not None
                ]
            )

    def __run_batch(self):
        if len(self.buffer) == 0:
            return
        logger.info("Running Batch of Topic Modelling")
        start = time.perf_counter()
        self.__process_batch()
        end = time.perf_counter()
        self.total_time += end - start
        logger.info(
            f"Processed {self.docs_added} documents, Total Topics: {len(self._topics)}, Time: {self.total_time:.2f}",
        )
        self.total_time = 0
        self.buffer = []
        if self.docs_added % self.merge_frequency == 0:
            self.merge_topics()

    def flush(self):
        self.__run_batch()

    def __update_centroids(self):
        if len(self._topics) == 0:
            return
        new_reduced_centroids = self.reducer.transform(
            [topic.embedding for topic in self._topics]
        )
        for topic, reduced_centroid in zip(self._topics, new_reduced_centroids):
            topic.centroid = normalize(reduced_centroid.squeeze())

    def __process_batch(self):
        embeddings = self.buffer

        if len(embeddings) > REDUCED_DIMENSIONS:
            self.reducer.fit_batch(embeddings)
            self.__update_centroids()

        reduced = normalize(self.reducer.transform(embeddings))

        for remb, emb in zip(reduced, embeddings):
            if len(self._topics) == 0:
                self._topics.append(
                    Topic(
                        id=shortuuid.uuid(),
                        support=1,
                        embedding=emb,
                        pca_centroid=remb,
                        is_fixed=False,
                        reducer=self.reducer,
                        min_sim_threshold=self.sim_threshold,
                    )
                )
                continue

            scores = [cosine(remb, c.centroid) for c in self._topics]
            best_score = np.max(scores).item()
            best_idx = np.argmax(scores).item()
            best_topic = self._topics[best_idx]

            can_merge = best_score > self.sim_threshold
            if best_topic.is_fixed:
                can_merge = best_score > self.fixed_sim_threshold

            if can_merge:
                best_topic.centroid = normalize(
                    weighted_average(
                        (
                            best_topic.centroid,
                            best_topic.support,
                        ),
                        (remb, 1),
                    )
                )
                best_topic.support += 1
                best_topic.embedding = normalize(
                    weighted_average(
                        (
                            best_topic.embedding,
                            best_topic.support,
                        ),
                        (emb, 1),
                    )
                )
            else:
                self._topics.append(
                    Topic(
                        id=shortuuid.uuid(),
                        support=1,
                        embedding=emb,
                        pca_centroid=remb,
                        is_fixed=False,
                        reducer=self.reducer,
                        min_sim_threshold=self.sim_threshold,
                    )
                )

    def merge_topics(self):
        try:
            old_topic_count = len(self._topics)
            merged = set()
            new_topics = []

            for i in range(len(self._topics)):
                if i in merged:
                    continue

                topic_i = self._topics[i].copy()

                for j in range(i + 1, len(self._topics)):
                    topic_j = self._topics[j]

                    if j in merged or topic_j.is_fixed:
                        continue

                    sim = cosine(topic_i.centroid, topic_j.centroid)

                    can_merge = sim > self.merge_threshold
                    if topic_i.is_fixed:
                        can_merge = sim > self.fixed_sim_threshold

                    if can_merge:
                        topic_i.merge(topic_j)
                        merged.add(j)

                if (
                    topic_i.support >= self.min_support
                    and topic_i.doc_count >= self.min_document_count
                ):
                    new_topics.append(topic_i)

            self._topics = new_topics
            logger.info(
                f"Merged {old_topic_count} topics down to {len(self._topics)} topics",
            )
        except Exception as e:
            traceback.print_exc()
            logger.exception(f"Error in merge: {e}", stack_info=True)

    @property
    def topics(self):
        return self._topics

    @property
    def num_topics(self):
        return len(self._topics)

    def save_topics(self):
        if len(self._topics) == 0:
            return
        db = Database()
        topics_to_delete = []
        for topic in self._topics:
            support = topic.sentence_count
            if support < self.min_support and not topic.is_fixed:
                topics_to_delete.append(topic.id)
                continue
            values = {
                "id": topic.id,
                "name": topic.name,
                "support": support,
                "doc_support": topic.doc_count,
                "embedding": topic.embedding.tolist(),
                "updated_at": datetime.datetime.now(datetime.timezone.utc),
                "is_fixed": topic.is_fixed,
            }
            insert_stmt = insert(TopicsTable).values(values)
            update_values = {k: v for k, v in values.items() if k != "id"}
            db.upsert(insert_stmt, "id", update_values)

        if len(topics_to_delete) > 0:
            with db.session() as session:  # type: Session
                session.execute(
                    delete(TopicsTable).where(TopicsTable.id.in_(topics_to_delete))
                )
            self._topics = [
                topic for topic in self._topics if topic.id not in topics_to_delete
            ]
        self.reducer.save()
        logger.info(f"Saved {len(self._topics)} topics")

    def get_topic(self, topic_id: int | str) -> Topic:
        if isinstance(topic_id, int):
            return self._topics[topic_id]

        for topic in self._topics:
            if topic.id == topic_id:
                return topic
        raise Exception(f"No Topic with id {topic_id} found")

    def label_topics(self):
        logger.info("Labelling Topics...")
        vectorizer = TfidfVectorizer()
        text = [[s.clean for s in topic.get_sentences()] for topic in self.topics]
        vectorizer.fit(flatten(text))
        for sentences, topic in zip(text, self._topics):
            if topic.is_fixed:
                logger.info("SKIPPING: ", topic.id)
                continue
            X = vectorizer.transform(sentences)
            tfidf_scores = np.asarray(X.mean(axis=0)).flatten()  # type: ignore
            words = np.array(vectorizer.get_feature_names_out())
            topic.name = ", ".join(words[np.argsort(tfidf_scores)[-5:]][::-1])
            logger.info(f"Topic {topic.id} = {topic.name}")
