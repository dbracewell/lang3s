import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import create_materialized_view

from . import Base
from .text_annotation import TextAnnotation
from .topic import Topic

selectable = sa.select(
    Topic.id.label("topic_id"),
    TextAnnotation.document_id,
    TextAnnotation.sentence_id,
    TextAnnotation.content,
    TextAnnotation.embedding.cosine_distance(Topic.embedding).label("cosine_distance"),
).where(
    TextAnnotation.type_ == "sentence",
    sa.not_(TextAnnotation.is_stopword),
    TextAnnotation.embedding.cosine_distance(Topic.embedding) <= 0.35,
)


class TopicSentences(Base):
    __table__ = create_materialized_view(
        name="topic_sentences",
        selectable=selectable,
        metadata=Base.metadata,
        indexes=[
            sa.Index("idx_topic_sentences_sentence_id", "sentence_id"),
            sa.Index("idx_topic_sentences_topic_id", "topic_id"),
            sa.Index("idx_topic_sentences_doc_id", "document_id"),
            sa.Index(
                "idx_topic_sentences_sentence_id_topic_id",
                "sentence_id",
                "topic_id",
                unique=True,
            ),
        ],
    )
    __mapper_args__ = {"primary_key": [__table__.c.sentence_id, __table__.c.topic_id]}
    topic_id: Mapped[int]
    sentence_id: Mapped[str]
    document_id: Mapped[str]
    content: Mapped[str]
    cosine_distance: Mapped[float]
