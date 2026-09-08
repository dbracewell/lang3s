from dataclasses import dataclass


@dataclass
class Cluster[T]:
    cluster_id: int
    items: list[T]


__all__ = ["Cluster"]
