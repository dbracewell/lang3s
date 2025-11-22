import enum
from typing import TYPE_CHECKING, List, NamedTuple, Tuple

import numpy as np
import torch
from numpy.typing import NDArray

if TYPE_CHECKING:
    pass


class TaskType(str, enum.Enum):
    SENTENCE = "sentence"
    SENTENCE_MULTILABEL = "sentence_multilabel"
    TOKEN = "token"

    def is_sentence_level(self) -> bool:
        return self.value == TaskType.SENTENCE_MULTILABEL or self.value == TaskType.SENTENCE

    def is_token(self) -> bool:
        return self.value == TaskType.TOKEN


class Chunk(NamedTuple):
    input_ids: List[torch.Tensor]
    attention_mask: List[torch.Tensor]
    word_ids: List[int]
    sentence_index: int
    start: int
    end: int


class SentenceTokenMapping(NamedTuple):
    token_count: int
    word_ids: List[int]


class ChunkResult(NamedTuple):
    chunks: List[Chunk]
    mapping: List[SentenceTokenMapping]


class EmbeddingResult(NamedTuple):
    word_embeddings: List[NDArray[np.floating]]
    sentence_embeddings: List[NDArray[np.floating]]
    token_embeddings: List[NDArray[np.floating]]
    mapping: List[SentenceTokenMapping]


class DechunkedResult(NamedTuple):
    token_embeddings: List[NDArray[np.floating]]
    word_embeddings: List[NDArray[np.floating]]


class TransformerOutput(NamedTuple):
    annotation_type: str
    task_type: TaskType
    labels: (List[Tuple[str | None, float]] |
             List[Tuple[List[str], list[float]]] |
             List[List[Tuple[int, int, str]]])
