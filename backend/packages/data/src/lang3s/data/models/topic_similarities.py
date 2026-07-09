from sqlalchemy import Double, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class TopicSimilarity(Base):
    __tablename__ = "topic_similarities"
    id1: Mapped[int] = mapped_column(
        "id1",
        ForeignKey("topics.id", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
    )
    id2: Mapped[int] = mapped_column(
        "id2",
        ForeignKey("topics.id", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
    )
    similarity: Mapped[float] = mapped_column(
        "similarity",
        Double,
        nullable=False,
    )

    __table_args__ = (Index("idx_topic_similarities_ids", "id1", "id2"),)

    def __repr__(self) -> str:
        return f"<%s id1={self.id1}, id2={self.id2}>" % self.__class__.__name__
