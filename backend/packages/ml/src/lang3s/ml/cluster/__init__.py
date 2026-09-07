from dataclasses import dataclass

from .hierarchical import ClusterNode, DivisiveKMeans
from .offline import DefaultOfflineClusterer
from .online import DefaultOnlineClusterer, ReducedCentroidCluster


@dataclass
class Cluster[T]:
    cluster_id: int
    items: list[T]


__all__ = [
    "Cluster",
    "DivisiveKMeans",
    "ClusterNode",
    "DefaultOnlineClusterer",
    "DefaultOfflineClusterer",
    "ReducedCentroidCluster",
]
