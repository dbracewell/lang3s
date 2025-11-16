from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from .text_annotation import TextAnnotation  # adjust if name/module differs
from .text_object import TextObject


class Text(TextObject):
    def __init__(
        self,
        doc_id: str,
        content: str,
        id: Optional[str] = ...,
        metadata: Optional[Dict[str, Any]] = ...,
        embedding: Optional[NDArray[np.floating]] = ...,
    ) -> None: ...

    # Internal collections
    _annotations: List[TextAnnotation]
    _tokens: List[TextAnnotation]
    _sentences: List[TextAnnotation]

    def get_annotation(self, id: Optional[str]) -> Optional[TextAnnotation]: ...

    @property
    def all_annotations(self) -> List[TextAnnotation]: ...

    def tag_data(
        self,
    ) -> Tuple[
        List[TextAnnotation],
        List[List[TextAnnotation]],
        List[List[str]],
    ]: ...

    @property
    def annotations(self) -> List[TextAnnotation]: ...

    def insert_values(self) -> List[Any]: ...

    def to_json(self) -> Dict[str, Any]: ...

    @staticmethod
    def from_json(obj: Dict[str, Any]) -> "Text": ...

    def add_annotation(
        self,
        text: str,
        start: int,
        end: int,
        sentence_id: int,
        type: str,
        value: str,
        source: str,
        id: Optional[str] = ...,
        embedding: Optional[NDArray[np.floating]] = ...,
        metadata: Optional[Dict[str, Any]] = ...,
    ) -> TextAnnotation: ...

    def attach_annotation(
        self,
        annotation: TextAnnotation,
    ) -> TextAnnotation: ...

    def remove_annotation(self, sources: List[str]) -> None: ...

    def create_span(
        self,
        start: int,
        end: int,
        source: str,
        type: Optional[str] = ...,
        value: Optional[str] = ...,
        metadata: Optional[Dict[str, Any]] = ...,
    ) -> TextAnnotation: ...
