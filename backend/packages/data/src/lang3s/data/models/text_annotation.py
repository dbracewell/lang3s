import datetime
from typing import Any, Optional

from pgvector import HalfVector
from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    ARRAY,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    and_,
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


class TextAnnotation(Base):
    __tablename__ = "text_annotations"
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
    cleaned: Mapped[str] = mapped_column(
        "cleaned",
        SqlAlchemyText,
        nullable=False,
    )
    normalized: Mapped[str] = mapped_column(
        "normalized",
        SqlAlchemyText,
        nullable=False,
        index=True,
    )
    start: Mapped[int] = mapped_column(
        "start",
        Integer,
        nullable=False,
    )
    end: Mapped[int] = mapped_column(
        "end",
        Integer,
        nullable=False,
    )
    type_: Mapped[str] = mapped_column(
        "type",
        String,
        nullable=False,
        index=True,
    )
    value: Mapped[str] = mapped_column(
        "value",
        String,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        "source",
        String,
        nullable=False,
    )
    mapping: Mapped[str] = mapped_column(
        "mapping",
        String,
        nullable=False,
        index=True,
    )
    sentence_index: Mapped[int] = mapped_column(
        "sentence_index",
        Integer,
        nullable=False,
    )
    sentence_id: Mapped[str] = mapped_column(
        "sentence_id",
        ForeignKey(
            "text_annotations.id",
            ondelete="CASCADE",
            name="fk_text_annotations_sentence_id",
        ),
        index=True,
    )
    is_stopword: Mapped[bool] = mapped_column(
        "is_stopword",
        Boolean,
        nullable=False,
        index=True,
    )
    embedding: Mapped[HalfVector] = mapped_column(
        "embedding",
        HALFVEC(config.SEMANTIC_EMBEDDING_DIMENSION),
        nullable=False,
    )
    # This field allows arbitrary properties to be store on the annotation.
    # This could include things like confidence scores, links to other annotations, etc.
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        MutableDict.as_mutable(JSONB),
        nullable=False,
        server_default="{}",
    )

    a0_text: Mapped[list[str]] = mapped_column(
        ARRAY(SqlAlchemyText),
        Computed(
            "jsonb_array_to_text_array(metadata->'A0_TEXT')",
            persisted=True,
        ),
    )
    # This field is used to pull out the normalized textual representation of the A1
    # roles for events
    a1_text: Mapped[list[str]] = mapped_column(
        ARRAY(SqlAlchemyText),
        Computed(
            "jsonb_array_to_text_array(metadata->'A1_TEXT')",
            persisted=True,
        ),
    )
    # This field is used to pull out the normalized textual representation of the time
    # role for events
    time_text: Mapped[Optional[str]] = mapped_column(
        String,
        Computed(
            "metadata->>'TIME_TEXT'",
            persisted=True,
        ),
        nullable=True,
        index=True,
    )
    # This field is used to pull out the normalized textual representation of the
    # location role for events
    loc_text: Mapped[Optional[str]] = mapped_column(
        String,
        Computed(
            "metadata->>'LOC_TEXT'",
            persisted=True,
        ),
        nullable=True,
        index=True,
    )
    # This field is used to pull out the text_annotation id of the A0 roles for events
    a0_id: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        Computed(
            "jsonb_array_to_text_array(metadata->'A0')",
            persisted=True,
        ),
    )
    # This field is used to pull out the text_annotation id of the A1 roles for events
    a1_id: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        Computed(
            "jsonb_array_to_text_array(metadata->'A1')",
            persisted=True,
        ),
    )
    # This field is used to pull out the text_annotation id of the time role for events
    time_id: Mapped[Optional[str]] = mapped_column(
        String,
        Computed("(metadata->>'TIME')", persisted=True),
        nullable=True,
    )
    # This field is used to pull out the text_annotation id of the location role for
    # events
    loc_id: Mapped[Optional[str]] = mapped_column(
        String,
        Computed("(metadata->>'LOC')", persisted=True),
        nullable=True,
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
    owner_id: Mapped[str] = mapped_column(
        "owner_id",
        ForeignKey(
            "texts.id",
            ondelete="CASCADE",
            name="fk_text_annotations_owner_id",
        ),
        index=True,
    )
    owner: Mapped[str] = relationship(
        "Text",
        back_populates="annotations",
    )

    __table_args__ = (
        Index(
            "idx_text_annotations_content_fts",
            "content",
            postgresql_using="pgroonga",
        ),
        Index(
            "idx_text_annotations_normalized_fts",
            "normalized",
            postgresql_using="pgroonga",
        ),
        Index(
            "idx_text_annotations_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
        ),
        Index(
            "idx_text_annotations_a0_text_gin_idx",
            "a0_text",
            postgresql_using="GIN",
        ),
        Index(
            "idx_text_annotations_a1_text_gin_idx",
            "a1_text",
            postgresql_using="GIN",
        ),
        Index(
            "idx_text_annotations_metadata_gin_idx",
            "metadata",
            postgresql_using="GIN",
            postgresql_ops={"metadata": "jsonb_path_ops"},
        ),
        Index(
            "ix_text_annotations_sentence_non_stopword_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={
                "m": 16,
                "ef_construction": 64,
            },
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
            postgresql_where=and_(type_ == "sentence", is_stopword.is_(False)),
        ),
        {"postgresql_partition_by": "HASH (id)"},
    )

    def __repr__(self) -> str:
        return f"<%s id={self.id}>" % self.__class__.__name__
