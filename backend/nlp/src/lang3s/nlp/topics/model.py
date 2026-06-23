from __future__ import annotations

import datetime
import time
import traceback
from typing import TYPE_CHECKING, Iterable, List

from sqlalchemy.orm import Session
from tqdm import tqdm

from lang3s import config
from lang3s.cluster.hierarchical import DivisiveKMeans
from lang3s.nlp.topics.naming import generate_cluster_node_name, label_topics
from lang3s.nlp.topics.reducer import OnlineReducer
from lang3s.nlp.topics.topic import Topic, TopicList
from lang3s.nlp.topics.topic_index import TopicIndex
from lang3s.utils.logger import get_logger

if TYPE_CHECKING:
    pass

import numpy as np
import shortuuid
from numpy.typing import NDArray
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

import lang3s.data.db.database as db
import lang3s.data.db.text_database as text_db
from lang3s.data.db.models import (
    TopicsTable,
    TopicsTreeTable,
    TopicTreeTopicMapTable,
)
from lang3s.nlp.shared_types import Document
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
        self._next_doc_id = 0
        self._topics: TopicList = TopicList()
        self._load_topics()

    def _load_topics(self):
        self.topic_index = TopicIndex(dimension=config.REDUCED_DIMENSIONS)
        self._topics.clear()

        session: Session
        with db.get_session() as session:
            for topic in session.scalars(select(TopicsTable)).all():
                self._topics.add_topic(
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

            if len(self._topics) == 0:
                return

            if not self.reducer.fitted:
                embeddings = []
                for sentence in text_db.random_sentences(5000, include_embedding=True):
                    embeddings.append(sentence["embedding"])

                if len(embeddings) > config.REDUCED_DIMENSIONS:
                    self.reducer.fit_batch(np.vstack(embeddings))
                    self._topics.renormalize_topic_embeddings(reducer=self.reducer)

            for topic in self._topics:
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

    def __process_batch(self):
        embeddings = np.array(self.buffer)
        if len(embeddings) == 0:
            return

        if len(embeddings) > config.REDUCED_DIMENSIONS:
            self.reducer.fit_batch(embeddings)
            if self._topics:
                self._topics.renormalize_topic_embeddings(reducer=self.reducer)
                for topic in self._topics:
                    self.topic_index.update_topic(
                        self.topic_index.topic2id[topic.id], topic.centroid
                    )

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

            topic = self._topics.create_new_topic(
                embedding=emb,
                pca_centroid=remb,
                reducer=self.reducer,
                min_sim_threshold=self.sim_threshold,
                document_id=doc_id,
            )
            self.topic_index.add_topic(topic)

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

            self._topics.update_topics([t[1] for t in updated_topics])
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
        return self._topics

    @property
    def num_topics(self):
        return len(self._topics)

    def save_topics(self):
        if len(self._topics) == 0:
            return

        to_delete = []
        to_upsert = []
        final_topics = []
        self._topics.update_sentence_counts()

        for topic_label, topic in tqdm(self.topic_index.topics()):
            if (
                topic.support < self.min_support
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
                "support": topic.support,
                "doc_support": topic.doc_count,
                "embedding": topic.embedding.tolist(),
                "updated_at": datetime.datetime.now(datetime.timezone.utc),
                "is_fixed": topic.is_fixed,
            }
            to_upsert.append(values)

            topic.doc_support += len(topic.doc_ids)
            topic.doc_ids.clear()
            final_topics.append((topic_label, topic))

        with db.get_session() as session:
            session.execute(delete(TopicsTable))
            session.execute(insert(TopicsTable).values(to_upsert))

        # Update the topic views (topic_sentences)
        db.refresh_topic_views()

        # Save the online PCA
        self.reducer.save()

        # Reload the topics to get all the correct ids
        self._load_topics()

        logger.info(f"💾 Saved {len(self._topics) - len(to_delete)} topics")

    def label_topics(self):
        logger.info("Labelling Topics...")
        label_topics(self._topics, logger)

    def build_hierarchical_topics(self):
        logger.info("Building Hierarchical Topics...")
        embeddings = [t.embedding for t in self._topics]
        clusterer = DivisiveKMeans(max_k=5, min_samples_leaf=5)
        clusterer.fit(embeddings, self._topics)
        tree_map = []
        joining_table = []
        if clusterer.root:
            frontier = [(None, clusterer.root)]
            while frontier:
                parent_id, next_node = frontier.pop()
                node_id = shortuuid.uuid()
                tree_map.append(
                    TopicsTreeTable(
                        id=node_id,
                        parent=parent_id,  # type: ignore
                        name=generate_cluster_node_name(next_node),
                        isLeaf=next_node.is_leaf,
                        splitK=next_node.k,
                    )
                )
                for item in next_node.items:
                    joining_table.append(
                        TopicTreeTopicMapTable(
                            nodeId=node_id,
                            topicId=item.id,
                        )
                    )
                for child in next_node.children:
                    frontier.append((node_id, child))

            with db.get_session() as session:
                session.execute(delete(TopicsTreeTable))
                session.execute(delete(TopicTreeTopicMapTable))
                session.bulk_save_objects(tree_map)
                session.bulk_save_objects(joining_table)


topic_model: Lang3sTopicModel = None  # type:ignore


def init_topic_model():
    global topic_model
    topic_model = Lang3sTopicModel()


def get_topic_model():
    if topic_model is None:
        print("No topic model available")
        raise Exception("topic model not initialized!")
    return topic_model
