from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import hnswlib
import numpy as np
from pydantic import ConfigDict, Field

from lang3s.core import config
from lang3s.data.schemas.topic import Topic
from lang3s.data.schemas.validators import NumpyArray
from lang3s.ml.decomposition import OnlineReducer
from lang3s.ml.math_extras import normalize, weighted_average


class TopicInfo(Topic):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    reduced_centroid: NumpyArray = Field(exclude=True)
    doc_ids: set[int] = Field(default_factory=set, exclude=True)
    last_updated: Optional[datetime] = Field(default=None, exclude=True)
    reducer: OnlineReducer = Field(exclude=True)
    min_sim_threshold: float = Field(exclude=True)
    is_existing: bool = Field(default=False, exclude=True)

    @property
    def updated_document_count(self) -> int:
        return self.document_count + len(self.doc_ids)

    def merge(self, other: TopicInfo) -> None:
        self.reduced_centroid = normalize(
            weighted_average(
                (self.reduced_centroid, self.sentence_count),
                (other.reduced_centroid, other.sentence_count),
            )
        )
        self.doc_ids.update(other.doc_ids)
        self.embedding = normalize(
            weighted_average(
                (self.embedding, self.sentence_count),
                (other.embedding, other.sentence_count),
            )
        )
        self.sentence_count += other.sentence_count
        self.last_updated = datetime.now()

    def add_sentence(
        self,
        doc_id: int,
        embedding: np.ndarray,
        reduced_embedding: np.ndarray,
    ) -> None:
        new_support = self.sentence_count + 1
        self.reduced_centroid = normalize(
            (self.reduced_centroid * self.sentence_count + reduced_embedding)
            / new_support
        )
        self.embedding = normalize(
            (self.embedding * self.sentence_count + embedding) / new_support
        )
        self.sentence_count = new_support
        self.last_updated = datetime.now()
        self.doc_ids.add(doc_id)

    def __repr__(self):
        return f"Topic(id={self.id}, name={self.name})"


@dataclass
class NearestNeighbor:
    topic: TopicInfo
    score: float


class TopicCollection:
    def __init__(self):
        self._dimension = config.REDUCED_DIMENSIONS
        self._max_elements = 1024
        self._next_topic_id = 0
        self._topic_map: dict[int, TopicInfo] = dict()
        self._index = None
        self.__init_index()

    def __init_index(self):
        self._index = hnswlib.Index(
            space="cosine",
            dim=self._dimension,
        )
        self._index.init_index(
            max_elements=self._max_elements,
            ef_construction=200,
            M=16,
        )
        self._next_topic_id = 0
        self._topic_map = dict()

    def _ensure_capacity(self, capacity: int):
        """Doubles the index capacity if we hit the limit."""
        if capacity >= self._max_elements:
            new_max = self._max_elements * 2
            self._index.resize_index(new_max)
            self._max_elements = new_max

    def remove_topic(self, label: int):
        if label in self._topic_map:
            self._index.mark_deleted(label)
            del self._topic_map[label]

    def update_topic(self, topic: TopicInfo):
        self._index.add_items(
            topic.reduced_centroid.reshape(1, -1),
            topic.id,
        )

    def find_best(
        self,
        centroid: np.ndarray,
        k: int = 20,
    ) -> NearestNeighbor | None:
        if not self._topic_map:
            return None
        try:
            labels, distances = self._index.knn_query(
                centroid.reshape(1, -1),
                k=k,
            )
            for i in range(k):
                label = int(labels[i][0])
                score = 1.0 - distances[i][0]
                if label in self._topic_map:
                    return NearestNeighbor(
                        topic=self._topic_map[label],
                        score=score,
                    )
        except RuntimeError:
            pass

        return None

    def rebuild(self, topics: list[TopicInfo]):
        self.__init_index()
        self._ensure_capacity(len(topics))
        self._next_topic_id = 0
        for topic in topics:
            self._index.add_items(topic.reduced_centroid.reshape(1, -1), topic.id)
            self._topic_map[topic.id] = topic  # type: ignore
            self._next_topic_id = max(self._next_topic_id, topic.id + 1)  # type:ignore

    def clear(self):
        self.__init_index()

    def __iter__(self):
        return iter(self._topic_map.values())

    def __len__(self):
        return len(self._topic_map)

    def __contains__(self, topic_id: int) -> bool:
        return topic_id in self._topic_map

    def merge_topics(self, topic_i: TopicInfo, topic_j: TopicInfo):
        topic_i.merge(topic_j)
        self.update_topic(topic_i)
        self.remove_topic(topic_j.id)  # type: ignore

    def renormalize_topic_embeddings(self, reducer: OnlineReducer) -> None:
        if self._topic_map:
            new_reduced_centroids = reducer.transform(
                np.vstack([topic.embedding for topic in self._topic_map.values()]),
            )
            for topic, reduced_centroid in zip(
                self._topic_map.values(), new_reduced_centroids
            ):
                topic.reduced_centroid = normalize(reduced_centroid.squeeze())
                self.update_topic(topic)

    def add_topic(self, topic: TopicInfo):
        self._ensure_capacity(len(self._topic_map) + 1)
        if topic.id is None:
            topic.id = self._next_topic_id
            self._next_topic_id += 1
        else:
            self._next_topic_id = max(self._next_topic_id, topic.id + 1)
        self._index.add_items(topic.reduced_centroid.reshape(1, -1), topic.id)
        self._topic_map[topic.id] = topic  # type: ignore

    def create_topic(
        self,
        embedding: np.ndarray,
        pca_centroid: np.ndarray,
        reducer: OnlineReducer,
        min_sim_threshold: float,
        document_id: int,
    ) -> TopicInfo:
        topic = TopicInfo(
            sentence_count=1,
            document_count=1,
            embedding=embedding,
            reduced_centroid=pca_centroid,
            is_fixed=False,
            reducer=reducer,
            min_sim_threshold=min_sim_threshold,
            last_updated=datetime.now(),
            doc_ids={document_id},
            name=f"topic-{self._next_topic_id}",
        )
        self.add_topic(topic)
        return topic
