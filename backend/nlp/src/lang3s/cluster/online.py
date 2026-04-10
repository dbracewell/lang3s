from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Sequence as SequenceType
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from lang3s.decomposition.online import OnlineReducer
from lang3s.utils.maths import cosine, normalize, weighted_average

from ..data.embedding import EmbeddingDB, LabeledItem
from . import Cluster


class OnlineClusterer[T](metaclass=ABCMeta):
    def fit(
        self,
        items: Sequence[T],
        embeddings: Sequence[np.ndarray],
    ) -> list[Cluster[T]]:
        for item, embedding in zip(items, embeddings):
            self.partial_fit(item, embedding)
        return self.finish()

    @abstractmethod
    def partial_fit(
        self,
        items: T | Sequence[T],
        embeddings: np.ndarray | list[np.ndarray],
    ) -> None: ...

    @abstractmethod
    def finish(self) -> list[Cluster[T]]: ...


@dataclass
class ReducedCentroidCluster[T](Cluster[T]):
    centroid: np.ndarray
    reduced_centroid: np.ndarray

    def add_item(
        self,
        item: T,
        embedding: np.ndarray,
        reduced_embedding: np.ndarray,
    ) -> None:
        self.items.append(item)
        self.centroid = normalize(
            (self.centroid * len(self.items) + embedding) / (len(self.items) + 1)
        )
        self.reduced_centroid = normalize(
            (self.reduced_centroid * len(self.items) + reduced_embedding)
            / (len(self.items) + 1)
        )

    def merge(
        self,
        other: ReducedCentroidCluster[T],
    ) -> None:
        self.centroid = normalize(
            weighted_average(
                (self.centroid, len(self.items)), (other.centroid, len(other.items))
            )
        )
        self.reduced_centroid = normalize(
            weighted_average(
                (self.reduced_centroid, len(self.items)),
                (other.reduced_centroid, len(other.items)),
            )
        )
        self.items.extend(other.items)


class DefaultOnlineClusterer[T](OnlineClusterer[T]):
    def __init__(
        self,
        n_components: int = 64,
        min_cluster_size: int = 5,
        epsilon: float = 0.65,
        merge_frequency: int = 5,
        merge_epsilon: float = 0.65,
        batch_size: int = 100,
    ):
        if n_components >= batch_size:
            print(
                "Reduced dimensions exceeds batch size, setting reduced_dimensions to max(64, batch_size//2)"
            )
            n_components = max(64, batch_size // 2)

        self.min_cluster_size = min_cluster_size
        self.epsilon = epsilon
        self.merge_frequency = merge_frequency
        self.merge_epsilon = merge_epsilon
        self.batch_size = batch_size
        self._batch: list[T] = []
        self._processed: int = 0
        self.reducer = OnlineReducer()
        self.reduced_dimensions = n_components
        self.index = EmbeddingDB[ReducedCentroidCluster[T]](
            dimension=self.reduced_dimensions
        )

    def fit(
        self,
        items: Sequence[T],
        embeddings: Sequence[np.ndarray],
    ) -> list[Cluster[T]]:
        for i in range(0, len(items), self.batch_size):
            self.partial_fit(
                items[i : i + self.batch_size], embeddings[i : i + self.batch_size]
            )
        return self.finish()

    def partial_fit(
        self, items: T | Sequence[T], embeddings: np.ndarray | Sequence[np.ndarray]
    ) -> None:
        if isinstance(items, SequenceType):
            self._batch.extend(zip(items, embeddings))
        else:
            self._batch.append((items, embeddings))

        if len(self._batch) >= self.batch_size:
            self._processed += len(self._batch)
            self.__process_batch()
            self._batch = []
            if self._processed >= self.merge_frequency * self.batch_size:
                self.__merge()
                self._processed = 0

    def finish(self) -> list[Cluster[T]]:
        if self._batch:
            self.__process_batch()
        self.__merge()
        return list(self.index.items.values())

    def __reduce_centroids(self):
        if self.index.count == 0:
            return
        reduced_centroids = self.reducer.transform(
            np.vstack([c.centroid for c in self.index.get_items()])
        )
        for new_reduced_centroid, labeled_item in zip(
            reduced_centroids, self.index.get_labeled_items()
        ):
            self.index.update(
                label=labeled_item.label,
                item=labeled_item.item,
                embedding=new_reduced_centroid,
            )

    def __create_new_cluster(
        self,
        item: T,
        embedding: np.ndarray,
        reduced_embedding: np.ndarray,
    ) -> ReducedCentroidCluster[T]:
        new_cluster = ReducedCentroidCluster(
            cluster_id=-1,
            items=[item],
            centroid=embedding,
            reduced_centroid=reduced_embedding,
        )
        new_cluster.cluster_id = self.index.add(new_cluster, reduced_embedding)
        return new_cluster

    def __process_batch(self):
        print(f"Processing batch: {len(self._batch)}")
        embeddings = np.vstack([embedding for _, embedding in self._batch])

        if len(embeddings) > self.reduced_dimensions:
            self.reducer.fit_batch(embeddings)
            self.__reduce_centroids()
        elif not self.reducer.fitted:
            raise RuntimeError("Reducer not fitted and not enough elements to fit")

        reduced = normalize(self.reducer.transform(embeddings))
        for (item, embedding), reduced_embedding in zip(self._batch, reduced):
            if self.index.count == 0:
                self.__create_new_cluster(
                    item=item,
                    embedding=embedding,
                    reduced_embedding=reduced_embedding,
                )
                continue

            query_results = self.index.query(reduced_embedding)
            if query_results:
                result = query_results[0]
                if result.score > self.epsilon:
                    centroid: ReducedCentroidCluster[T] = result.item
                    centroid.add_item(item, embedding, reduced_embedding)
                    self.index.update(
                        label=result.label,
                        item=centroid,
                        embedding=centroid.reduced_centroid,
                    )
                    continue

            self.__create_new_cluster(
                item=item,
                embedding=embedding,
                reduced_embedding=reduced_embedding,
            )

    def __merge(self):
        self._merge_docs = 0
        clusters = self.index.get_labeled_items()
        updated_clusters: list[
            tuple[LabeledItem[ReducedCentroidCluster[T]], np.ndarray]
        ] = []

        merged = set()
        for i in range(len(clusters)):
            if i in merged:
                continue

            cluster_i = clusters[i]

            for j in range(i + 1, len(clusters)):
                cluster_j = clusters[j]

                if j in merged:
                    continue

                sim = cosine(cluster_i.item.centroid, cluster_j.item.centroid)
                if sim >= self.merge_epsilon:
                    cluster_i.item.merge(cluster_j.item)
                    merged.add(j)

            if len(cluster_i.item.items) >= self.min_cluster_size:
                updated_clusters.append((cluster_i, cluster_i.item.reduced_centroid))

        self.index.rebuild(updated_clusters)
