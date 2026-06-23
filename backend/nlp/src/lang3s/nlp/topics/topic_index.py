from typing import Dict, List, Tuple

import hnswlib

from .topic import Topic


class TopicIndex:
    def __init__(self, dimension, initial_max=1024):
        self.dim = dimension
        self.max_elements = initial_max
        self.index = None
        self.count = 0
        self.topic_map: Dict[int, Topic] = dict()
        self.topic2id: Dict[str | int, int] = dict()
        self.max_neighbors = 10
        self.__init_index()

    def __init_index(self):
        self.index = hnswlib.Index(space="cosine", dim=self.dim)
        self.index.init_index(
            max_elements=self.max_elements,
            ef_construction=200,
            M=16,
        )
        self.topic_map = dict()
        self.topic2id = dict()

    def topics(self):
        return list(self.topic_map.items())

    def _ensure_capacity(self, capacitiy):
        """Doubles the index capacity if we hit the limit."""
        if capacitiy >= self.max_elements:
            new_max = self.max_elements * 2
            self.index.resize_index(new_max)
            self.max_elements = new_max

    def add_topic(self, topic_obj):
        self._ensure_capacity(self.count)
        label = self.count
        self.index.add_items(topic_obj.centroid.reshape(1, -1), label)
        self.topic_map[label] = topic_obj
        self.topic2id[topic_obj.id] = label
        self.count += 1
        return label

    def remove_topic(self, label: int):
        """Removes a topic from the search index and the mapping."""
        if label in self.topic_map:
            # mark_deleted keeps the label from being returned in searches
            self.index.mark_deleted(label)
            del self.topic_map[label]
            topic_id = None
            for tid, tlbl in self.topic2id.items():
                if label == tlbl:
                    topic_id = tid
                    break
            if topic_id:
                del self.topic2id[topic_id]

    def update_topic(self, label, centroid):
        self.index.add_items(centroid.reshape(1, -1), label)

    def find_best(self, remb):
        if not self.topic_map:
            return None, None, 0.0
        try:
            labels, distances = self.index.knn_query(
                remb.reshape(1, -1), k=self.max_neighbors
            )
            for i in range(self.max_neighbors):
                label = int(labels[i][0])
                score = 1.0 - distances[i][0]
                if label in self.topic_map:
                    return label, self.topic_map[label], score
        except RuntimeError:  # Occurs if index is empty
            pass

        return None, None, 0.0

    def rebuild(self, topics: List[Tuple[int, Topic]]):
        self.__init_index()
        self._ensure_capacity(len(topics))
        for label, topic_obj in topics:
            self.index.add_items(topic_obj.centroid.reshape(1, -1), label)
            self.topic_map[label] = topic_obj
            self.topic2id[topic_obj.id] = label
