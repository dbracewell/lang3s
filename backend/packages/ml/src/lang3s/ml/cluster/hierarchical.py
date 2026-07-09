import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


class ClusterNode:
    def __init__(self, items, k=None):
        self.items = items
        self.k = k
        self.children = []
        self.is_leaf = k is None

    def traverse(self, labels, level=0):
        if self.is_leaf:
            return f"Leaf ({self.items})\n"
        else:
            res = ""
            for child in self.children:
                res += child.traverse(labels, level + 1)
            return res


class DivisiveKMeans:
    def __init__(self, max_k=5, min_samples_leaf=2):
        self.max_k = max_k
        self.min_samples_leaf = min_samples_leaf
        self.root: ClusterNode | None = None

    def fit(self, embeddings: list[np.ndarray], items):
        if embeddings:
            X = np.vstack(embeddings)
            ids = np.arange(X.shape[0])
            self.root = self._split(X, ids, items)
        return self

    def _split(self, X, ids, items):
        n_samples = X.shape[0]

        if n_samples <= self.min_samples_leaf:
            return ClusterNode([items[i] for i in ids])

        best_k = 2
        best_labels = None
        max_score = -1.0

        limit = min(self.max_k, n_samples - 1)
        if limit < 2:
            return ClusterNode([items[i] for i in ids])

        for k in range(2, limit + 1):
            kmeans = KMeans(n_clusters=k, n_init="auto", random_state=42)
            labels = kmeans.fit_predict(X)

            # Check if k is valid (some k might result in empty clusters in edge cases)
            unique_labels = len(np.unique(labels))
            if unique_labels < 2:
                continue

            score = silhouette_score(X, labels)

            if score > max_score:
                max_score = score
                best_k = k
                best_labels = labels

        node = ClusterNode([items[i] for i in ids], k=best_k)

        if best_labels is not None:
            for k_idx in range(best_k):
                mask = best_labels == k_idx
                subset_X = X[mask]
                subset_ids = ids[mask]

                # Only recurse if the cluster has points
                if len(subset_ids) > 0:
                    node.children.append(self._split(subset_X, subset_ids, items))
            return node
        else:
            return ClusterNode([items[i] for i in ids])
