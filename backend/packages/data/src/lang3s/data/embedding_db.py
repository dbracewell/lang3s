from typing import NamedTuple

import hnswlib
import numpy as np


class QueryResult[T](NamedTuple):
    item: T
    score: float
    label: int


class LabeledItem[T](NamedTuple):
    item: T
    label: int


class EmbeddingDB[T]:
    def __init__(self, dimension, initial_max=1024):
        self.dim = dimension
        self.max_elements = initial_max
        self.index = None
        self.count = 0
        self.items: dict[int, T]
        self.__init_index()

    def __init_index(self):
        self.index = hnswlib.Index(space="cosine", dim=self.dim)
        self.index.init_index(
            max_elements=self.max_elements,
            ef_construction=200,
            M=16,
        )
        self.items = dict()

    def _ensure_capacity(self, capacity):
        """Doubles the index capacity if we hit the limit."""
        if capacity >= self.max_elements:
            new_max = self.max_elements * 2
            self.index.resize_index(new_max)
            self.max_elements = new_max

    def add(
        self,
        item: T,
        embedding: np.ndarray,
    ) -> int:
        self._ensure_capacity(self.count)
        label = self.count
        self.index.add_items(embedding.reshape(1, -1), label)
        self.items[label] = item
        self.count += 1
        return label

    def __getitem__(self, label: int) -> T | None:
        if label in self.items:
            return self.items[label]
        return None

    def get_items(self) -> list[T]:
        return list(self.items.values())

    def get_labeled_items(self) -> list[LabeledItem[T]]:
        return [LabeledItem(item=v, label=k) for k, v in self.items.items()]

    def update(
        self,
        label,
        embedding: np.ndarray | None = None,
        item: T | None = None,
    ) -> None:
        if embedding is not None:
            self.index.add_items(embedding.reshape(1, -1), label)
        if item is not None:
            self.items[label] = item

    def clear(self) -> None:
        self.__init_index()

    def remove(self, label):
        if label in self.items:
            self.index.mark_deleted(label)
            del self.items[label]

    def query(self, embedding: np.ndarray, max_neighbors=10) -> list[QueryResult[T]]:
        results: list[QueryResult[T]] = []

        if not self.items:
            return results

        try:
            labels, distances = self.index.knn_query(
                embedding.reshape(1, -1), k=max_neighbors
            )
            for i in range(len(labels)):
                label = int(labels[i][0])
                score = 1.0 - distances[i][0]
                if label in self.items:
                    results.append(
                        QueryResult(item=self.items[label], score=score, label=label)
                    )
        except RuntimeError:  # Occurs if index is empty
            pass

        return results

    def rebuild(self, items: list[tuple[LabeledItem[T], np.ndarray]]) -> None:
        self.__init_index()
        self._ensure_capacity(len(items))
        for item, embedding in items:
            self.index.add_items(embedding.reshape(1, -1), item.label)
            self.items[item.label] = item.item
