# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
import weakref
from typing import Any, Dict, Optional, Mapping  # for IDEs only
from psycopg.types.json import Jsonb

from .text cimport Text
from .metadata import Metadata
from .db_columns import DocumentRow

cdef class Document:
    """
    Cython-optimized Document object replacing the Python DBModel/Deserializable version.
    """

    def __cinit__(self):
        self._meta = ListMetadata()

    def __init__(
        self,
        str doc_id,
        str title,
        Text text,
        dict metadata = None
    ):
        self.id = doc_id
        self.title = title
        self.text = text

        if metadata is not None:
            for k, v in metadata.items():
                self[k] = v

    def __contains__(self, item: str):
        return self._meta.get(item, None) is not None

    def __setitem__(self, str key, object value):
        self._meta.set(key, value)

    def __delitem__(self, str key):
        self._meta.set(key, None)

    def __getitem__(self, str item):
        return self._meta.get(item, None)

    # ------------------------------------------------------------
    # JSON serialization
    # ------------------------------------------------------------
    cpdef dict to_json(self):
        return {
            "id": self.id,
            "title": self.title,
            "metadata": self._meta.to_dict(),
            "text": self.text.to_json(),
        }

    def __str__(self):
        return f"Document(id={self.id}, title={self.title})"

    def __repr__(self):
        return f"Document(id={self.id}, title={self.title})"

    @staticmethod
    def from_json(obj: Dict[str, Any]) -> "Document":
        """
        Rebuild a Document from JSON.
        """
        from .text import Text  # local import to avoid circular issues

        text = Text.from_json(obj)
        return Document(
            doc_id=obj["id"],
            title=obj["title"],
            metadata=obj.get("metadata", {}),
            text=text,  #type: ignore
        )

    cpdef list insert_values(self):
        return list(DocumentRow(id=self.id, title=self.title, metadata=Jsonb(self._meta.to_dict())))

    @property
    def language(self):
        return self[Metadata.LANGUAGE.value] or "en"

    cpdef void detach(self):
        if self.text is not None:
            self.text.detach()
        self.text = None
        self._meta = None
