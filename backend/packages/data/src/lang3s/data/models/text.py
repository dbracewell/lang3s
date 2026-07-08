from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from pgvector import HalfVector
from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy import (
    Text as SqlAlchemyText,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lang3s.core import config

from . import Base

if TYPE_CHECKING:
    from .document import Document
    from .text_annotation import TextAnnotation


class Text(Base):
    __tablename__ = "texts"
    id: Mapped[str] = mapped_column(
        "id",
        String(22),
        primary_key=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        "content",
        SqlAlchemyText,
        nullable=False,
    )
    embedding: Mapped[HalfVector] = mapped_column(
        "embedding",
        HALFVEC(config.SEMANTIC_EMBEDDING_DIMENSION),
        nullable=False,
    )
    # This field allows arbitrary properties to be store on the text.
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        MutableDict.as_mutable(JSONB),
        nullable=False,
        server_default="{}",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    document_id: Mapped[str] = mapped_column(
        "document_id",
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
            name="fk_text_document_id",
        ),
        index=True,
    )

    document: Mapped[Document] = relationship(
        "Document",
        back_populates="text",
    )

    annotations: Mapped[list[TextAnnotation]] = relationship(
        "TextAnnotation",
        back_populates="owner",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "idx_texts_content_fts",
            "content",
            postgresql_using="pgroonga",
            postgresql_with={"tokenizer": "'TokenBigramSplitSymbolAlphaDigit'"},
        ),
        Index(
            "idx_texts_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
        ),
        Index(
            "idx_texts_metadata_gin_idx",
            "metadata",
            postgresql_using="GIN",
            postgresql_ops={"metadata": "jsonb_path_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<%s id={self.id}>" % self.__class__.__name__
