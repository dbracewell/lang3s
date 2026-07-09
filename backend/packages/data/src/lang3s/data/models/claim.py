import datetime
import enum
import uuid

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    ARRAY,
    UUID,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from lang3s.core import config

from . import Base


class ClaimType(enum.StrEnum):
    Fact = enum.auto()
    Definition = enum.auto()
    Value = enum.auto()
    Policy = enum.auto()
    Causation = enum.auto()
    Comparison = enum.auto()
    Contingency = enum.auto()


class Modality(enum.StrEnum):
    factual = enum.auto()
    normative = enum.auto()
    hypothetical = enum.auto()
    conditional = enum.auto()
    predictive = enum.auto()


class Certainty(enum.StrEnum):
    certain = enum.auto()
    probable = enum.auto()
    possible = enum.auto()
    speculative = enum.auto()
    unknown = enum.auto()


class Sentiment(
    enum.StrEnum,
):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"


class Claim(
    Base,
):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(
        "id",
        UUID(
            as_uuid=True,
        ),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
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
    claim: Mapped[str] = mapped_column(
        "claim",
        Text,
        nullable=False,
    )
    type_: Mapped[str] = mapped_column(
        "claim_type",
        Enum(ClaimType, name="claim_type_enum"),
        nullable=False,
        index=True,
    )
    source = mapped_column(
        "source",
        String,
        nullable=True,
    )
    subject = mapped_column(
        "subject",
        String,
        nullable=False,
        index=True,
    )
    predicate = mapped_column(
        "predicate",
        String,
        nullable=False,
        index=True,
    )
    object = mapped_column(
        "object",
        String,
        nullable=False,
        index=True,
    )
    stance = mapped_column(
        "stance",
        String,
        nullable=False,
    )
    certainty = mapped_column(
        "certainty",
        Enum(Certainty, name="certainty_enum"),
        nullable=False,
    )
    modality = mapped_column(
        "modality",
        Enum(Modality, name="modality_enum"),
        nullable=False,
    )
    negation = mapped_column(
        "negation",
        Boolean,
        nullable=False,
    )
    condition = mapped_column(
        "condition",
        String,
        nullable=True,
    )
    time = mapped_column(
        "time",
        String,
        nullable=True,
    )
    location = mapped_column(
        "location",
        String,
        nullable=True,
    )
    evidence = mapped_column(
        "evidence",
        String,
        nullable=True,
    )
    sentiment = mapped_column(
        "sentiment",
        Enum(
            Sentiment,
            name="sentiment_enum_type",
        ),
        nullable=False,
    )
    keywords = mapped_column(
        "keywords",
        ARRAY(
            String,
        ),
        nullable=False,
    )
    embedding: Mapped[list] = mapped_column(
        "embedding",
        HALFVEC(
            config.SEMANTIC_EMBEDDING_DIMENSION,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        "created_at",
        DateTime(
            timezone=True,
        ),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        "updated_at",
        DateTime(
            timezone=True,
        ),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "idx_claims_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
        ),
    )

    def __repr__(
        self,
    ) -> str:  # pragma: no cover
        return f"<%s id={self.id}>" % self.__class__.__name__
