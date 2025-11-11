import enum
from typing import TYPE_CHECKING, Dict, List, NamedTuple, Optional, Tuple, Union

import numpy as np
import torch
from numpy.typing import NDArray

if TYPE_CHECKING:
    from .heads import TaskHead


class TaskType(str, enum.Enum):
    SENTENCE = "sentence"
    TOKEN = "token"


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
    labels: Union[List[str], List[List[Tuple[int, int, str]]]]


class Adapter:
    def __init__(
        self,
        task_name: str,
        label2id: Dict[str, int],
        annotation_type: str,
        task_type: TaskType,
        language: Optional[str] = None,
    ) -> None:
        self.annotation_type = annotation_type
        self.language = language
        self.label2id = label2id
        self.id2label = {v: k for k, v in label2id.items()}
        self.task_type = task_type
        self.task_name = task_name
        self.head: Optional[TaskHead] = None

    def to_json(self):
        return {
            "annotation_type": self.annotation_type,
            "language": self.language,
            "label2id": self.label2id,
            "task_type": self.task_type.value,
            "task_name": self.task_name,
        }
