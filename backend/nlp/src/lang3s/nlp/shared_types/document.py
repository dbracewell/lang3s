from dataclasses import dataclass, field
from typing import Any, Dict

from psycopg.types.json import Jsonb

from lang3s.nlp.metadata import Metadata

from .db_columns import DocumentRow
from .text import Text


@dataclass(slots=True)
class Document:
    text: Text
    title: str
    id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __contains__(self, item: str):
        return item in self.metadata

    def __setitem__(self, key: str, value: Any):
        self.metadata[key] = value

    def __delitem__(self, key: str):
        if key in self.metadata:
            del self.metadata[key]

    def __getitem__(self, item: str):
        return self.metadata.get(item, None)

    def to_json(self):
        return {
            "id": self.id,
            "title": self.title,
            "metadata": self.metadata,
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
            id=obj["id"],
            title=obj["title"],
            metadata=obj.get("metadata", {}),
            text=text,
        )

    def insert_values(self):
        return list(
            DocumentRow(id=self.id, title=self.title, metadata=Jsonb(self.metadata))
        )

    @property
    def language(self):
        return self[Metadata.LANGUAGE.value] or "en"

    def detach(self):
        if self.text is not None:
            self.text.detach()
            del self.text
        self.text = None  # type: ignore
        self.metadata.clear()
