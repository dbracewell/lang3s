from typing import Annotated, Any

import numpy as np
from pydantic import BeforeValidator, PlainSerializer


def coerce_to_numpy(v: Any) -> np.ndarray:
    if isinstance(v, np.ndarray):
        return v
    try:
        return np.asarray(v)
    except Exception as e:
        raise ValueError(f"Could not convert to numpy array: {e}")


type NumpyArray = Annotated[
    np.ndarray,
    BeforeValidator(coerce_to_numpy),
    PlainSerializer(lambda x: x.tolist(), return_type=list[float], when_used="always"),
]
