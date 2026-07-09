from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .ontology import Ontology

from . import Base


class AnnotationOntologyMapping(Base):
    __tablename__ = "annotation_ontology_mappings"

    id: Mapped[int] = mapped_column(
        "id",
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True,
    )
    mapping: Mapped[str] = mapped_column(
        "mapping",
        String,
        nullable=False,
        index=True,
    )
    ontology_id: Mapped[int] = mapped_column(
        "ontology_id",
        ForeignKey("ontology.id", ondelete="CASCADE"),
        index=True,
    )

    ontology_item: Mapped[Ontology] = relationship(
        "Ontology",
        back_populates="mappings",
    )

    __table_args__ = (
        UniqueConstraint(
            "mapping",
            "ontology_id",
            name="uniq_annotation_ontology_mapping_ontology_id",
        ),
    )

    def __repr__(self) -> str:
        return f"<%s id={self.id}>" % self.__class__.__name__
