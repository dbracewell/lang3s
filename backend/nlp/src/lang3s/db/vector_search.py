from typing import List, Tuple

import hnswlib
import numpy as np

from lang3s.maths import cosine


class VectorDB:
    def __init__(
        self,
        dim: int,
        max_elements: int = 100_000,
        ef_construction: int = 400,
        M: int = 64,
    ):
        """
        dim: embedding dimension (e.g. 768)
        max_elements: maximum number of vectors you expect
        ef_construction: defines accuracy/speed tradeoff during index building
        M: number of bi-directional links per element (16–64 typical)
        """
        self.dim = dim
        self.max_elements = max_elements
        self.vectors = []

        # Initialize index for cosine similarity
        self.index = hnswlib.Index(space="cosine", dim=dim)
        self.index.init_index(
            max_elements=max_elements,
            ef_construction=ef_construction,
            M=M,
            allow_replace_deleted=True,  # type: ignore
        )
        self.index.set_ef(400)  # search accuracy parameter

        self.id_to_pos = {}  # map external IDs to internal HNSW positions
        self.next_pos = 0

    def add_vector(self, id: int, vector: np.ndarray):
        self.vectors.append(vector)
        return
        """Add a new vector (if the ID exists, it will overwrite it)."""
        vector = np.asarray(vector, dtype=np.float32).reshape(1, -1)

        # Remove old entry if it exists
        if id in self.id_to_pos:
            self.update_vector(id, vector)
            return

        pos = self.next_pos
        self.index.add_items(vector, np.array([pos], dtype=np.int32))
        self.id_to_pos[id] = pos
        self.next_pos += 1

    def update_vector(self, id: int, vector: np.ndarray):
        self.vectors[id] = vector
        return
        """Remove and reinsert the vector for the given ID."""
        vector = np.asarray(vector, dtype=np.float32).reshape(1, -1)

        if id not in self.id_to_pos:
            # if new, just add
            self.add_vector(id, vector)
            return

        pos = self.id_to_pos[id]
        # HNSWlib does not support in-place updates → we mark and reinsert
        self.index.add_items(
            vector, np.array([pos], dtype=np.int32), replace_deleted=True
        )

    def search(
        self, vector: np.ndarray, k: int = 10
    ) -> Tuple[List[int], List[float]]:
        sims = [cosine(vector, c) for c in self.vectors]
        return [i for i in range(len(self.vectors))], sims

        """Return (distances, ids) for the k nearest neighbors."""
        vector = np.asarray(vector, dtype=np.float32).reshape(1, -1)
        labels, distances = self.index.knn_query(
            vector, k=min(k, len(self.id_to_pos))
        )

        # convert internal positions back to user IDs
        inv_map = {v: k for k, v in self.id_to_pos.items()}
        result_ids = []
        result_distances = []
        for label, distance in zip(labels[0], distances[0]):
            if int(label) in inv_map:
                result_ids.append(inv_map[int(label)])
                result_distances.append(1 - distance)

        return result_ids, result_distances

    def get_vector(self, id):
        return self.vectors[id]
        return np.array(
            self.index.get_items(np.array([self.id_to_pos[id]], dtype=np.int32))
        )

    def __len__(self):
        return len(self.vectors)
        return len(self.id_to_pos)
