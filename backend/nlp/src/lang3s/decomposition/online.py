import os

import joblib
import numpy as np
from sklearn.decomposition import IncrementalPCA


class OnlineReducer:
    def __init__(self, reduced_dimensions: int = 64):
        self.pca = IncrementalPCA(n_components=reduced_dimensions)
        self.fitted = False

    def fit_batch(self, batch):
        self.pca.partial_fit(batch)
        self.fitted = True

    def transform(self, vectors):
        if not self.fitted:
            raise RuntimeError("PCA not fitted yet.")
        return self.pca.transform(vectors).astype(np.float32)

    def save(self, model_file: str):
        joblib.dump(self.pca, model_file)

    @staticmethod
    def load(model_file: str, throw_on_error: bool = True):
        reducer = OnlineReducer()
        if os.path.exists(model_file):
            reducer.pca = joblib.load(model_file)
            reducer.fitted = True
        elif throw_on_error:
            raise FileNotFoundError(model_file)
        return reducer
