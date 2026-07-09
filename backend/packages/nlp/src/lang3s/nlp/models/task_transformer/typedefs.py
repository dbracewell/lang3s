import enum
from typing import List, Tuple, TypeAlias

MultiClassResult: TypeAlias = List[Tuple[str | None, float]]
MultiLabelResult: TypeAlias = List[Tuple[List[str], list[float]]]
TokenLabelResult: TypeAlias = List[List[Tuple[str, int, int]]]
TransformerResult: TypeAlias = MultiClassResult | MultiLabelResult | TokenLabelResult


class TaskType(str, enum.Enum):
    SENTENCE = "sentence"
    SENTENCE_MULTILABEL = "sentence_multilabel"
    TOKEN = "token"

    def is_sentence_level(self) -> bool:
        return (
            self.value == TaskType.SENTENCE_MULTILABEL
            or self.value == TaskType.SENTENCE
        )

    def is_token(self) -> bool:
        return self.value == TaskType.TOKEN
