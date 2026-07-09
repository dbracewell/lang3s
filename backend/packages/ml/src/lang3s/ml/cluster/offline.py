from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections import defaultdict
from typing import Any, Literal, Sequence

import numpy as np
import umap
from sklearn.cluster import HDBSCAN, AgglomerativeClustering, KMeans

from . import Cluster


class OfflineClusterer[T](metaclass=ABCMeta):
    @abstractmethod
    def fit(
        self,
        items: Sequence[T],
        embeddings: Sequence[np.ndarray],
    ) -> list[Cluster[T]]: ...


class DefaultOfflineClusterer[T](OfflineClusterer[T]):
    def __init__(
        self,
        min_cluster_size: int = 5,
        distance_threshold: Any = None,
        metric: str = "cosine",
        n_components: int = 64,
        n_clusters: int = None,
        clustering_algorithm: Literal["hdbscan", "agglomerative", "kmeans"] = "hdbscan",
        linkage_method: Literal["average", "ward", "single", "complete"] = "average",
    ):
        self.min_cluster_size = min_cluster_size
        self.distance_threshold = distance_threshold
        self.metric = metric
        self.n_components = n_components
        self.clustering_algorithm = clustering_algorithm
        self.linkage = linkage_method
        self.n_clusters = n_clusters

    def fit(
        self,
        items: Sequence[T],
        embeddings: Sequence[np.ndarray],
    ) -> list[Cluster[T]]:
        reduced = umap.UMAP(
            n_components=self.n_components,
            metric=self.metric,
        ).fit_transform(embeddings)

        if self.clustering_algorithm == "hdbscan":
            clusterer = HDBSCAN(
                min_cluster_size=self.min_cluster_size,
                cluster_selection_epsilon=self.distance_threshold or 0.0,
                metric=self.metric,
            )
            labels = clusterer.fit_predict(reduced)
        elif self.clustering_algorithm == "agglomerative":
            clusterer = AgglomerativeClustering(
                n_clusters=self.n_clusters,
                metric=self.metric,
                linkage=self.linkage,
                distance_threshold=self.distance_threshold,
            )
            labels = clusterer.fit_predict(reduced)
        elif self.clustering_algorithm == "kmeans":
            clusterer = KMeans(
                n_clusters=self.n_clusters,
            )
            labels = clusterer.fit_predict(reduced)
        else:
            raise ValueError(f"Unknown clustering type: {self.clustering_algorithm}")

        clusters = defaultdict(lambda: Cluster(cluster_id=-1, items=[]))
        for label, item in zip(labels, items):
            if label == -1:
                continue
            cluster = clusters[label]
            cluster.cluster_id = label
            cluster.items.append(item)

        return [c for c in clusters.values() if len(c.items) >= self.min_cluster_size]
