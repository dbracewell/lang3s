import datetime
import uuid

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import Boolean, DateTime, Index, Integer, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from lang3s.core import config

from . import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(
        "id",
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        "name",
        Text,
        nullable=False,
    )
    is_fixed: Mapped[bool] = mapped_column(
        "is_fixed",
        Boolean,
        nullable=False,
    )
    embedding: Mapped[list] = mapped_column(
        "embedding",
        HALFVEC(config.SEMANTIC_EMBEDDING_DIMENSION),
        nullable=False,
    )
    sentence_count: Mapped[int] = mapped_column(
        "sentence_count",
        Integer,
        nullable=False,
    )
    document_count: Mapped[int] = mapped_column(
        "document_count",
        Integer,
        nullable=False,
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

    __table_args__ = (
        Index(
            "idx_topics_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<%s id={self.id}>" % self.__class__.__name__
