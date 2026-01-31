import logging
from typing import Tuple

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


def remap(value, old_min, old_max, new_min, new_max):
    """
    Linearly maps a value from one range [old_min, old_max] to [new_min, new_max].
    """
    if old_max - old_min == 0:
        return new_min  # Avoid division by zero
    return new_min + (value - old_min) * (new_max - new_min) / (old_max - old_min)


def binarize(v: NDArray[np.floating]) -> str:
    return "".join((str(i) for i in (v > 0).astype(int).tolist()))


def normalize(v: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    if v.ndim == 1:
        norm = np.linalg.norm(v) + eps
        safe_norm = np.where(norm == 0, 1, norm)
        return v / safe_norm

    norm = np.linalg.norm(v, axis=-1, keepdims=True) + eps
    safe_norms = np.where(norm == 0, 1, norm)
    return v / safe_norms


def cosine(
    n1: NDArray[np.floating],
    n2: NDArray[np.floating],
):
    if n1.shape[0] == 1 and n2.shape[0] == 1:
        n1 = n1.squeeze()
        n2 = n2.squeeze()

    return np.clip(
        np.dot(n1, n2) / (np.linalg.norm(n1) * np.linalg.norm(n2) + 1e-12), 0, 1
    )


def weighted_average(
    *args: Tuple[NDArray[np.floating], float],
) -> NDArray[np.floating]:
    if len(args) == 0:
        raise Exception("Must pass in at least one argument")
    vector_sums: NDArray[np.floating] = args[0][0] * args[0][1]
    weight_sums: float = args[0][1]

    for i in range(1, len(args)):
        vector_sums = vector_sums + args[i][0] * args[i][1]
        weight_sums += args[i][1]

    if weight_sums == 0:
        return vector_sums

    return vector_sums / weight_sums
