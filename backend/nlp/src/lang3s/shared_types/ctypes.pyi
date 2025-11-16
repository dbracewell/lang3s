from typing import Optional, Dict, Any, List

import numpy as np
from numpy._typing import NDArray


class TextObject:
    text: str
    start: int
    end: int
    doc_id: str
    lemma: str
    is_stopword: bool

    def to_string(self,
                  ignore_stopwords=False,
                  lemmatize=False,
                  lowercase=False) -> str: ...

    def interleave(self, interleaved: str) -> List["TextAnnotation"]: ...

    def __getitem__(self, item: str) -> Any: ...

    def __setitem__(self, key: str, value: Any): ...


class TextAnnotation(TextObject):

    def to_json(self) -> Dict[str, Any]: ...


class Text:
    text: str
    start: int
    end: int
    doc_id: str
    lemma: str
    is_stopword: bool

    def __init__(self,
                 doc_id: str,
                 content: str,
                 id: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 embedding: Optional[NDArray[np.floating]] = None, ) -> None: ...

    def add_annotation(
        self,
        text: str,
        start: int,
        end: int,
        sentence_id: int,
        type: str,
        value: str,
        id: Optional[str] = None,
        embedding: Optional[NDArray[np.floating]] = None,
        metadata: Dict[str, Any] | None = None,
    ) -> "TextAnnotation": ...

    def annotations_of_type(self, type: str) -> List["TextAnnotation"]: ...

    def to_json(self) -> Dict[str, Any]: ...
