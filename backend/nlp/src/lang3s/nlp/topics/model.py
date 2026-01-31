import datetime
import logging
import time
import traceback
from typing import TYPE_CHECKING, Iterable, List

from sqlalchemy.orm import Session

from lang3s import config
from lang3s.nlp.topics.reducer import OnlineReducer
from lang3s.nlp.topics.topic import Topic
from lang3s.nlp.topics.topic_index import TopicIndex

if TYPE_CHECKING:
    pass

import numpy as np
import shortuuid
import sqlalchemy
from numpy.typing import NDArray
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import Boolean, Select, cast, delete, select
from sqlalchemy.dialects.postgresql import insert

from lang3s.data.db import Database
from lang3s.data.db.models import TextAnnotationsTable, TopicsTable
from lang3s.nlp.shared_types import Document
from lang3s.utils import flatten
from lang3s.utils.maths import cosine, normalize
from lang3s.utils.meta import SingletonMeta

logger = logging.getLogger("TopicModel")


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
        self._batch_docs: int = 0
        self._merge_docs: int = 0
        self.sentences_added: int = 0
        self.total_time = 0
        self.buffer: List[NDArray[np.floating]] = []
        self.buffer_ids: List[int] = []
        self.reducer = OnlineReducer.load()
        self.topic_index = TopicIndex(dimension=config.REDUCED_DIMENSIONS)
        self._load_topics()
        self._next_topic_id = 0
        self._next_doc_id = 0

    def _load_topics(self):
        db = Database()
        topics = []
        session: Session
        with db.session() as session:
            for topic in session.scalars(select(TopicsTable)).all():
                topics.append(
                    Topic(
                        id=topic.id,
                        support=topic.support,
                        embedding=topic.embedding.to_numpy(),
                        pca_centroid=np.zeros(config.REDUCED_DIMENSIONS),
                        is_fixed=topic.fixed,
                        name=topic.name,
                        reducer=self.reducer,
                        min_sim_threshold=self.sim_threshold,
                        doc_support=topic.documents,
                    )
                )

            if len(topics) == 0:
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
                    embeddings.append(sentence.embedding.to_numpy())  # type:ignore

                if len(embeddings) > config.REDUCED_DIMENSIONS:
                    self.reducer.fit_batch(np.vstack(embeddings))
                    new_reduced_centroids = self.reducer.transform(
                        np.vstack([topic.embedding for topic in topics])
                    )
                    for topic, reduced_centroid in zip(topics, new_reduced_centroids):
                        topic.centroid = normalize(reduced_centroid.squeeze())

            for topic in topics:
                self.topic_index.add_topic(topic)

    def partial_fit_sentence_embeddings(
        self,
        embeddings: List[List[float]]
        | List[NDArray[np.floating]]
        | NDArray[np.floating],
    ):
        self.docs_added += 1
        self._batch_docs += 1
        self._merge_docs += 1
        if isinstance(embeddings, list):
            self.sentences_added += len(embeddings)
        else:
            self.sentences_added += embeddings.shape[0]

        if isinstance(embeddings, list):
            if isinstance(embeddings[0], list):
                self.buffer.extend([normalize(np.array(e)) for e in embeddings])
            else:
                self.buffer.extend([normalize(e) for e in embeddings])  # type: ignore
        else:
            self.buffer.extend([normalize(e) for e in embeddings])
        self.buffer_ids.extend([self._next_doc_id for _ in embeddings])
        self._next_doc_id += 1

        if self._batch_docs >= self.batch_size:
            self._batch_docs = 0
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
            f"Processed {self.docs_added} documents, Total Topics: {len(self.topic_index.topic_map)}, Time: {self.total_time:.2f}",
        )
        self.total_time = 0
        self.buffer = []
        self.buffer_ids = []
        if self._merge_docs >= self.merge_frequency:
            self.merge_topics()

    def flush(self):
        self.__run_batch()

    def _add_new_topic(self, doc_id, emb, remb):
        topic = Topic(
            id=f"topic-{self._next_topic_id}",
            support=1,
            embedding=emb,
            pca_centroid=remb,
            is_fixed=False,
            reducer=self.reducer,
            min_sim_threshold=self.sim_threshold,
        )
        topic.doc_ids.add(doc_id)
        self._next_topic_id += 1
        self.topic_index.add_topic(topic)

    def __process_batch(self):
        embeddings = np.array(self.buffer)
        if len(embeddings) == 0:
            return

        if len(embeddings) > config.REDUCED_DIMENSIONS:
            self.reducer.fit_batch(embeddings)
            topics = self.topic_index.topics()
            if topics:
                embeddings_to_transform = np.vstack(
                    [topic.embedding for _, topic in topics]
                )
                new_reduced_centroids = self.reducer.transform(embeddings_to_transform)
                for (topic_idx, topic), reduced_centroid in zip(
                    topics, new_reduced_centroids
                ):
                    topic.centroid = normalize(reduced_centroid.squeeze())
                    self.topic_index.update_topic(topic_idx, topic.centroid)

        reduced = normalize(self.reducer.transform(embeddings))

        for i, (remb, emb, doc_id) in enumerate(
            zip(reduced, embeddings, self.buffer_ids)
        ):
            best_idx, best_topic, best_score = self.topic_index.find_best(remb)

            if best_idx is not None:
                current_threshold = (
                    self.fixed_sim_threshold
                    if best_topic.is_fixed
                    else self.sim_threshold
                )
                if best_score > current_threshold:
                    new_support = best_topic.support + 1
                    best_topic.centroid = normalize(
                        (best_topic.centroid * best_topic.support + remb) / new_support
                    )
                    best_topic.embedding = normalize(
                        (best_topic.embedding * best_topic.support + emb) / new_support
                    )
                    best_topic.support = new_support
                    self.topic_index.update_topic(best_idx, best_topic.centroid)
                    self.topic_index.topic_map[best_idx].doc_ids.add(doc_id)
                    continue

            self._add_new_topic(doc_id, emb, remb)

        self.buffer = []  # Clear memory

    def merge_topics(self):
        self._merge_docs = 0
        topics: list[tuple[int, Topic]] = self.topic_index.topics()
        updated_topics: list[tuple[int, Topic]] = []

        try:
            start = time.perf_counter()
            old_topic_count = len(self.topic_index.topic_map)
            merged = set()

            for i in range(len(topics)):
                if i in merged:
                    continue

                topic_i_idx, topic_i = topics[i]

                for j in range(i + 1, len(topics)):
                    topic_j_idx, topic_j = topics[j]

                    if j in merged or topic_j.is_fixed:
                        continue

                    sim = cosine(topic_i.centroid, topic_j.centroid)

                    can_merge = sim > self.merge_threshold
                    if topic_i.is_fixed:
                        can_merge = sim > self.fixed_sim_threshold

                    if can_merge:
                        topic_i.merge(topic_j)
                        self.topic_index.update_topic(topic_i_idx, topic_i.centroid)
                        merged.add(j)

                if (
                    topic_i.support >= self.min_support
                    and topic_i.doc_count >= self.min_document_count
                ):
                    updated_topics.append((topic_i_idx, topic_i))

            self.topic_index.rebuild(updated_topics)
            end = time.perf_counter()
            logger.info(
                f"Merged {old_topic_count} topics down to {len(self.topic_index.topic_map)} topics in {end - start:.2f} seconds",
            )
        except Exception as e:
            traceback.print_exc()
            logger.exception(f"Error in merge: {e}", stack_info=True)

    @property
    def topics(self):
        return [topic for _, topic in self.topic_index.topics()]

    @property
    def num_topics(self):
        return len(self.topic_index.topic_map)

    def save_topics(self):
        topics = self.topic_index.topics()

        if len(topics) == 0:
            return

        db = Database()
        to_delete = []
        to_upsert = []
        final_topics = []

        for topic_label, topic in topics:
            if (
                topic.sentence_count < self.min_support
                and topic.doc_count < self.min_document_count
                and not topic.is_fixed
            ):
                to_delete.append(topic.id)
                self.topic_index.remove_topic(topic_label)
                continue

            # 2. ID Generation
            if topic.id.startswith("topic-"):
                topic.id = shortuuid.uuid()

            # 3. Prepare Batch Data
            values = {
                "id": topic.id,
                "name": topic.name,
                "support": topic.sentence_count,
                "doc_support": topic.doc_count,
                "embedding": topic.embedding.tolist(),
                "updated_at": datetime.datetime.now(datetime.timezone.utc),
                "is_fixed": topic.is_fixed,
            }
            to_upsert.append(values)

            topic.doc_support += len(topic.doc_ids)
            topic.doc_ids.clear()
            final_topics.append((topic_label, topic))

        with db.session() as session:
            if to_upsert:
                stmt = insert(TopicsTable).values(to_upsert)
                update_cols = {
                    col: stmt.excluded[col]
                    for col in to_upsert[0].keys()
                    if col != "id"
                }
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=["id"], set_=update_cols
                )
                session.execute(upsert_stmt)

            if to_delete:
                session.execute(
                    delete(TopicsTable).where(TopicsTable.id.in_(to_delete))
                )

            session.commit()

        # db = Database()
        # to_delete = []
        # final_topics = []
        # for topic_label, topic in topics:
        #     support = topic.sentence_count
        #     doc_count = topic.doc_count
        #
        #     if (
        #         support < self.min_support
        #         and doc_count < self.min_document_count
        #         and not topic.is_fixed
        #     ):
        #         to_delete.append(topic.id)
        #         self.topic_index.remove_topic(topic_label)
        #         continue
        #
        #     topic_id = topic.id
        #     if topic_id.startswith("topic-"):
        #         topic_id = shortuuid.uuid()
        #         topic.id = topic_id
        #
        #     values = {
        #         "id": topic_id,
        #         "name": topic.name,
        #         "support": support,
        #         "doc_support": doc_count,
        #         "embedding": topic.embedding.tolist(),
        #         "updated_at": datetime.datetime.now(datetime.timezone.utc),
        #         "is_fixed": topic.is_fixed,
        #     }
        #     topic.doc_support = doc_count
        #     topic.doc_ids.clear()
        #     final_topics.append((topic_label, topic))
        #
        #     self._next_doc_id = 0
        #     insert_stmt = insert(TopicsTable).values(values)
        #     update_values = {k: v for k, v in values.items() if k != "id"}
        #     db.upsert(insert_stmt, "id", update_values)
        #
        # if len(to_delete) > 0:
        #     with db.session() as session:  # type: Session
        #         session.execute(
        #             delete(TopicsTable).where(TopicsTable.id.in_(to_delete))
        #         )

        self.topic_index.rebuild(final_topics)
        self.reducer.save()
        db.refresh_topic_views()
        logger.info(f"Saved {len(topics) - len(to_delete)} topics")

    def get_topic(self, topic_id: int | str) -> Topic:
        if isinstance(topic_id, int):
            return self.topic_index.topic_map[topic_id]

        for _, topic in self.topic_index.topics():
            if topic.id == topic_id:
                return topic
        raise Exception(f"No Topic with id {topic_id} found")

    def label_topics(self):
        logger.info("Labelling Topics...")
        vectorizer = TfidfVectorizer()
        text = [[s.clean for s in topic.get_sentences()] for topic in self.topics]
        vectorizer.fit(flatten(text))
        for sentences, (topic_idx, topic) in zip(text, self.topic_index.topics()):
            if topic.is_fixed:
                logger.info("SKIPPING: ", topic.id)
                continue
            X = vectorizer.transform(sentences)
            tfidf_scores = np.asarray(X.mean(axis=0)).flatten()  # type: ignore
            words = np.array(vectorizer.get_feature_names_out())
            topic.name = ", ".join(words[np.argsort(tfidf_scores)[-5:]][::-1])
            logger.info(f"Topic {topic.id} = {topic.name}")


topic_model: Lang3sTopicModel = None  # type:ignore


def init_topic_model():
    global topic_model
    topic_model = Lang3sTopicModel()


def get_topic_model():
    if topic_model is None:
        print("No topic model available")
        raise Exception("topic model not initialized!")
    return topic_model
