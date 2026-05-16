from __future__ import annotations

import datetime
import textwrap
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Iterable, List

from joblib import Parallel, delayed
from sqlalchemy.orm import Session
from tqdm import tqdm

from lang3s import config
from lang3s.llm import LLMClient, Message
from lang3s.nlp.topics.reducer import OnlineReducer
from lang3s.nlp.topics.topic import Topic
from lang3s.nlp.topics.topic_index import TopicIndex
from lang3s.utils.logger import get_logger

if TYPE_CHECKING:
    pass

import numpy as np
import shortuuid
import sqlalchemy
from numpy.typing import NDArray
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import Boolean, Select, cast, delete, func, select, text
from sqlalchemy.dialects.postgresql import insert

import lang3s.data.db.database as db
from lang3s.data.db.models import TextAnnotationsTable, TopicsTable
from lang3s.nlp.shared_types import Document
from lang3s.utils import flatten, try_catch
from lang3s.utils.maths import cosine, normalize
from lang3s.utils.meta import SingletonMeta

logger = get_logger("TOPIC_MODEL")


DB_COLUMNS = [
    "id",
    "support",
    "embedding",
    "is_fixed",
    "name",
]


def create_topic_name(topic: Topic) -> str:
    client = LLMClient()
    sentences = [t.text for t in topic.get_sentences(limit=10)]
    prompt = textwrap.dedent(f"""
                    Given the following sentences and list of keywords generate a short phrase that defines the topic.
                    Make the phrase generic and not specific to ONE keyword or sentence it should be generic enough to cover the entier set of sentences and keywords.
                    Give no explanation or reasoning for your answer only the answer and in plain text NO MARKUP.

                    Keywords:
                    {topic.name}

                    Sentences:
                    {"\n".join(sentences)}
                """).strip()
    response = client.sync_chat_completion_last_event([Message.user(prompt)])
    if response.exception:
        return topic.name
    return response.content.title()


def topic_naming(topics: list[Topic]):
    with try_catch(on_error=lambda e: logger.error(e)):
        with Parallel(
            n_jobs=-1,
            prefer="threads",
            mmap_mode="shared",
        ) as parallel:
            return parallel([delayed(create_topic_name)(v) for v in topics])

    return [t.name for t in topics]


class Lang3sTopicModel(metaclass=SingletonMeta):
    def __init__(
        self,
    ):
        self.sim_threshold: float = config.get_config_value(
            "topics_similarity_threshold", 0.45
        )
        self.fixed_sim_threshold: float = config.get_config_value(
            "topics_fixed_similarity_threshold", 0.6
        )
        self.merge_threshold: float = config.get_config_value(
            "topics_merge_threshold", 0.65
        )
        self.fixed_merge_threshold: float = config.get_config_value(
            "topics_fixed_merge_threshold", 0.75
        )
        self.min_support: int = config.get_config_value("topics_min_support", 10)
        self.min_document_count: int = config.get_config_value(
            "topics_min_document_count", 4
        )
        self.batch_size: int = config.get_config_value("topics_batch_size", 100)
        self.merge_frequency: int = config.get_config_value(
            "topics_merge_frequency", 400
        )

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
        topics = []
        session: Session
        with db.get_session() as session:
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
            last_updated=datetime.datetime.now(),
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
                    best_topic.last_updated = datetime.datetime.now()
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

        to_delete = []
        to_upsert = []
        not_updated = []
        final_topics = []

        with ThreadPoolExecutor(max_workers=20) as executor:
            sentence_counts = list(
                executor.map(_get_topic_count, [t[1].embedding for t in topics])
            )

        for sentence_count, (topic_label, topic) in tqdm(zip(sentence_counts, topics)):
            if not topic.last_updated:
                not_updated.append(topic)
                continue

            if (
                sentence_count < self.min_support
                and topic.doc_count < self.min_document_count
                and not topic.is_fixed
            ):
                to_delete.append(topic.id)
                self.topic_index.remove_topic(topic_label)
                continue

            if topic.id.startswith("topic-"):
                topic.id = shortuuid.uuid()

            values = {
                "id": topic.id,
                "name": topic.name,
                "support": sentence_count,
                "doc_support": topic.doc_count,
                "embedding": topic.embedding.tolist(),
                "updated_at": datetime.datetime.now(datetime.timezone.utc),
                "is_fixed": topic.is_fixed,
            }
            to_upsert.append(values)

            topic.doc_support += len(topic.doc_ids)
            topic.doc_ids.clear()
            final_topics.append((topic_label, topic))

        if to_delete:
            with db.get_session() as session:
                # First transaction delete merged topics
                session.execute(
                    delete(TopicsTable).where(TopicsTable.id.in_(to_delete))
                )

        if to_upsert:
            with db.get_session() as session:
                # second transaction upsert topics
                stmt = insert(TopicsTable).values(to_upsert)
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=[TopicsTable.id],
                    set_={
                        c.name: stmt.excluded[c.name]
                        for c in TopicsTable.__table__.columns  # type:ignore
                        if c.name != "id"
                    },
                )
                session.execute(upsert_stmt)

        # Update the topic views (topic_sentences)
        db.refresh_topic_views()

        # Save the online PCA
        self.reducer.save()

        # Rebuild the topic index
        self.topic_index.rebuild(final_topics)

        logger.info(f"💾 Saved {len(topics) - len(to_delete)} topics")

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
        to_name = []
        for sentences, (topic_idx, topic) in zip(text, self.topic_index.topics()):
            if topic.is_fixed:
                logger.info("SKIPPING: ", topic.id)
                continue

            to_name.append(topic)
            X = vectorizer.transform(sentences)
            tfidf_scores = np.asarray(X.mean(axis=0)).flatten()  # type: ignore
            words = np.array(vectorizer.get_feature_names_out())
            topic.name = ", ".join(words[np.argsort(tfidf_scores)[-5:]][::-1])

        results = topic_naming(to_name)
        for topic, name in zip(to_name, results):
            print(topic.id, topic.is_fixed, topic.name, name)
            if not topic.is_fixed:
                topic.name = name
                self.topic_index.topics()
            logger.info(f"Topic {topic.id} = {topic.name}")


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


topic_model: Lang3sTopicModel = None  # type:ignore


def init_topic_model():
    global topic_model
    topic_model = Lang3sTopicModel()


def get_topic_model():
    if topic_model is None:
        print("No topic model available")
        raise Exception("topic model not initialized!")
    return topic_model
