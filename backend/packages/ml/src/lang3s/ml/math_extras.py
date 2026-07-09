import numpy as np
from scipy.spatial.distance import cosine as scipy_cosine


def remap(value, old_min, old_max, new_min, new_max):
    """
    Linearly maps a value from one range [old_min, old_max] to [new_min, new_max].
    """
    if old_max - old_min == 0:
        return new_min  # Avoid division by zero
    return new_min + (value - old_min) * (new_max - new_min) / (old_max - old_min)


def cosine(
    n1: np.ndarray,
    n2: np.ndarray,
):
    sim = 1.0 - scipy_cosine(n1.ravel(), n2.ravel())
    return float(np.clip(sim, -1.0, 1.0))


def normalize(v: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / (norm + eps)


def weighted_average(
    *args: tuple[np.ndarray, float],
) -> np.ndarray:
    if not args:
        raise ValueError("Must pass in at least one argument")

    arrays, weights = zip(*args)
    weight_sum = sum(weights)

    if weight_sum == 0:
        return sum(w * arr for arr, w in args)  # type: ignore

    return np.average(arrays, axis=0, weights=weights)
