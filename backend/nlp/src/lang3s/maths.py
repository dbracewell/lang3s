import logging
from typing import Tuple

import numpy as np
from numpy.typing import NDArray

logger = logging.Logger(__name__)


def binarize(v: NDArray[np.floating]) -> str:
    return "".join((str(i) for i in (v > 0).astype(int).tolist()))


def normalize(
    v: NDArray[np.floating],
) -> NDArray[np.floating]:
    if v.ndim == 1:
        return (v / np.linalg.norm(v)).astype(np.float16)
    return (v / np.linalg.norm(v, axis=1, keepdims=True)).astype(np.float16)


def cosine(
    n1: NDArray[np.floating],
    n2: NDArray[np.floating],
):
    if n1.shape[0] == 1 and n2.shape[0] == 1:
        n1 = n1.squeeze()
        n2 = n2.squeeze()
    return np.dot(n1, n2) / (np.linalg.norm(n1) * np.linalg.norm(n2) + 1e-12)


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
    return vector_sums / weight_sums
