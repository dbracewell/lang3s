from __future__ import annotations

import asyncio
import time
import traceback
from typing import Iterable, List

import numpy as np
from lang3s.ml.decomposition import OnlineReducer
from lang3s.ml.math_extras import cosine, normalize
from numpy.typing import NDArray
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm import tqdm

from lang3s.core import config
from lang3s.core.formatters import format_duration
from lang3s.core.logger import get_logger
from lang3s.core.typing_extras import SingletonMeta
from lang3s.data.repositories.text_repository import TextRepository
from lang3s.data.repositories.topic_repository import TopicRepository
from lang3s.data.schemas import Document

from .schemas import TopicCollection, TopicInfo
from .topic_naming import label_topics

logger = get_logger("TOPIC_MODEL")


class Lang3sTopicModel(metaclass=SingletonMeta):
    def __init__(
        self,
        session: AsyncSession,
    ):
        self.session: AsyncSession = session
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

        self._docs_added: int = 0
        self._merge_docs: int = 0
        self._buffer: List[NDArray[np.floating]] = []
        self._buffer_ids: List[int] = []
        reducer_path = config.MODELS_DIR / "topic_reducer.pkl"
        if reducer_path.exists():
            self._reducer = OnlineReducer.load(reducer_path, throw_on_error=False)
        else:
            self._reducer = OnlineReducer(config.REDUCED_DIMENSIONS)
        self._next_doc_id = 0
        self._topics: TopicCollection = TopicCollection()
        self._to_remove: List[TopicInfo] = []
        self._load_topics()

    async def _load_topics(self):
        self._topics.clear()
        for topic in await TopicRepository(self.session).list_topics():
            self._topics.add_topic(
                TopicInfo(
                    **topic.model_dump(),
                    reduced_centroid=np.zeros(config.REDUCED_DIMENSIONS),
                    min_sim_threshold=self.sim_threshold,
                    reducer=self._reducer,
                    is_existing=True,
                )
            )

        if len(self._topics) == 0:
            return

        if not self._reducer.fitted:
            embeddings = []
            for sentence in await TextRepository(self.session).get_random_sentences(
                5000,
            ):
                embeddings.append(sentence.embedding)

            if len(embeddings) > config.REDUCED_DIMENSIONS:
                self._reducer.fit_batch(np.vstack(embeddings))
                self._topics.renormalize_topic_embeddings(reducer=self._reducer)

    def partial_fit_sentence_embeddings(
        self,
        embeddings: List[List[float]] | List[np.ndarray] | np.ndarray,
    ):
        self._docs_added += 1
        self._merge_docs += 1

        if isinstance(embeddings, list):
            if isinstance(embeddings[0], list):
                self._buffer.extend([normalize(np.array(e)) for e in embeddings])
            else:
                self._buffer.extend([normalize(e) for e in embeddings])  # type: ignore
        else:
            self._buffer.extend([normalize(e) for e in embeddings])

        self._buffer_ids.extend([self._next_doc_id for _ in embeddings])
        self._next_doc_id += 1

        if self._docs_added >= self.batch_size:
            self.__run_batch()
            self._docs_added = 0

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
        if len(self._buffer) == 0:
            return
        start = time.perf_counter()
        self.__process_batch()

        logger.info(
            f"Processed a batch of {self._docs_added} documents, "
            f"Total Topics: {len(self._topics)}, "
            f"Time: {format_duration(start, time.perf_counter())}",
        )
        self._buffer = []
        self._buffer_ids = []
        if self._merge_docs >= self.merge_frequency:
            self.merge_topics()

    def flush(self):
        if self._buffer:
            self.__run_batch()
            self.merge_topics()

    def __process_batch(self):
        embeddings = np.array(self._buffer)
        if len(embeddings) == 0:
            return

        if len(embeddings) > config.REDUCED_DIMENSIONS:
            self._reducer.fit_batch(embeddings)
            self._topics.renormalize_topic_embeddings(reducer=self._reducer)

        reduced = normalize(self._reducer.transform(embeddings))

        for i, (remb, emb, doc_id) in enumerate(
            zip(reduced, embeddings, self._buffer_ids)
        ):
            neighbor = self.topics.find_best(remb)

            if neighbor:
                current_threshold = (
                    self.sim_threshold
                    if not neighbor.topic.is_fixed
                    else self.fixed_sim_threshold
                )
                if neighbor.score > current_threshold:
                    neighbor.topic.add_sentence(
                        doc_id=doc_id,
                        embedding=emb,
                        reduced_embedding=remb,
                    )
                    self._topics.update_topic(neighbor.topic)
                    continue

            self._topics.create_topic(
                embedding=emb,
                pca_centroid=remb,
                reducer=self._reducer,
                min_sim_threshold=self.sim_threshold,
                document_id=doc_id,
            )

        self._buffer = []  # Clear memory

    def merge_topics(self):
        self._merge_docs = 0
        topics: list[TopicInfo] = list(self._topics)
        updated_topics: list[TopicInfo] = []

        try:
            start = time.perf_counter()
            old_topic_count = len(self._topics)
            merged = set()

            for i in range(len(topics)):
                if i in merged:
                    continue

                topic_i = topics[i]

                for j in range(i + 1, len(topics)):
                    topic_j = topics[j]

                    if j in merged or topic_j.is_fixed:
                        continue

                    sim = cosine(topic_i.reduced_centroid, topic_j.reduced_centroid)

                    can_merge = sim > self.merge_threshold
                    if topic_i.is_fixed:
                        can_merge = sim > self.fixed_sim_threshold

                    if can_merge:
                        self._topics.merge_topics(topic_i, topic_j)
                        if topic_j.is_existing:
                            self._to_remove.append(topic_j)
                        merged.add(j)

                if self._has_enough_support(topic_i):
                    updated_topics.append(topic_i)

            self._topics.rebuild(updated_topics)
            end = time.perf_counter()
            logger.info(
                f"Merged {old_topic_count} topics down to "
                f"{len(self._topics)} topics in {end - start:.2f} seconds"
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

    def _has_enough_support(self, topic: TopicInfo) -> bool:
        return (
            topic.sentence_count >= self.min_support
            and topic.updated_document_count >= self.min_document_count
        )

    async def save_topics(self):
        if len(self._topics) == 0:
            return

        repository: TopicRepository = TopicRepository(self.session)
        to_upsert: list[TopicInfo] = []
        final_topics: list[TopicInfo] = []

        for topic in self._topics:
            sc, dc = await repository.get_support_for_topic(topic.embedding)
            topic.sentence_count = sc
            topic.document_count = dc

        for topic in tqdm(self._topics):
            if not topic.is_fixed and not self._has_enough_support(topic):
                if topic.is_existing:
                    self._to_remove.append(topic)
                continue

            if not topic.is_existing:
                topic.id = None

            topic.document_count += len(topic.doc_ids)
            topic.doc_ids.clear()
            to_upsert.append(topic)
            final_topics.append(topic)

        await repository.delete_in([t.id for t in self._to_remove if t.id is not None])
        self._to_remove.clear()

        await self.label_topics()
        await repository.update_topics(to_upsert)

        # Update the topic views (topic_sentences)
        # db.refresh_topic_views()

        # Save the online PCA
        self._reducer.save(config.MODELS_DIR / "topic_reducer.pkl")

        # Reload the topics to get all the correct ids
        await self._load_topics()

        logger.info(f"💾 Saved {len(self._topics)} topics")

    async def label_topics(self):
        logger.info("Labelling Topics...")
        await label_topics(self._topics, self.session, logger)

    # def build_hierarchical_topics(self):
    #     logger.info("Building Hierarchical Topics...")
    #     embeddings = [t.embedding for t in self._topics]
    #     clusterer = DivisiveKMeans(max_k=5, min_samples_leaf=5)
    #     clusterer.fit(embeddings, self._topics)
    #     tree_map = []
    #     joining_table = []
    #     if clusterer.root:
    #         frontier = [(None, clusterer.root)]
    #         while frontier:
    #             parent_id, next_node = frontier.pop()
    #             node_id = shortuuid.uuid()
    #             tree_map.append(
    #                 TopicsTreeTable(
    #                     id=node_id,
    #                     parent=parent_id,  # type: ignore
    #                     name=generate_cluster_node_name(next_node),
    #                     isLeaf=next_node.is_leaf,
    #                     splitK=next_node.k,
    #                 )
    #             )
    #             for item in next_node.items:
    #                 joining_table.append(
    #                     TopicTreeTopicMapTable(
    #                         nodeId=node_id,
    #                         topicId=item.id,
    #                     )
    #                 )
    #             for child in next_node.children:
    #                 frontier.append((node_id, child))
    #
    #         with db.get_session() as session:
    #             session.execute(delete(TopicsTreeTable))
    #             session.execute(delete(TopicTreeTopicMapTable))
    #             session.bulk_save_objects(tree_map)
    #             session.bulk_save_objects(joining_table)


topic_model: Lang3sTopicModel = None  # type:ignore


def init_topic_model(session: AsyncSession):
    global topic_model
    topic_model = Lang3sTopicModel(session)


def get_topic_model():
    if topic_model is None:
        print("No topic model available")
        raise Exception("topic model not initialized!")
    return topic_model
