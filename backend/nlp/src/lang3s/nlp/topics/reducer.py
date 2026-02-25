from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

import joblib
import numpy as np
from sklearn.decomposition import IncrementalPCA

from lang3s import config


class OnlineReducer:
    def __init__(self):
        self.pca = IncrementalPCA(n_components=config.REDUCED_DIMENSIONS)
        self.fitted = False

    def fit_batch(self, batch):
        self.pca.partial_fit(batch)
        self.fitted = True

    def transform(self, vectors):
        if not self.fitted:
            raise RuntimeError("PCA not fitted yet.")
        return self.pca.transform(vectors).astype(np.float32)

    def save(self):
        output_file = os.path.join(config.MODELS_DIR, "online_reducer.pkl")
        joblib.dump(self.pca, output_file)

    @staticmethod
    def load():
        model_file = os.path.join(config.MODELS_DIR, "online_reducer.pkl")
        reducer = OnlineReducer()
        if os.path.exists(model_file):
            reducer.pca = joblib.load(model_file)
            reducer.fitted = True
        return reducer
