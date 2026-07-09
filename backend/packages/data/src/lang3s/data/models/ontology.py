from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_utils import Ltree, LtreeType

if TYPE_CHECKING:
    from .annotation_ontology_mapping import AnnotationOntologyMapping

from . import Base


class Ontology(Base):
    __tablename__ = "ontology"

    id: Mapped[int] = mapped_column(
        "id",
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        "name",
        String,
        nullable=False,
        unique=True,
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        "parent_id",
        ForeignKey("ontology.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        "description",
        Text,
        nullable=True,
    )
    color: Mapped[str] = mapped_column(
        "color",
        String,
        nullable=False,
    )
    path: Mapped[Ltree] = mapped_column(
        "path",
        LtreeType,
        nullable=False,
    )
    properties: Mapped[dict[str, Any]] = mapped_column(
        "properties",
        MutableDict.as_mutable(JSONB),
        nullable=False,
        server_default="{}",
    )

    mappings: Mapped[list[AnnotationOntologyMapping]] = relationship(
        "AnnotationOntologyMapping",
        back_populates="ontology_item",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    parent: Mapped[Optional[Ontology]] = relationship(
        "Ontology",
        remote_side="Ontology.id",
        back_populates="children",
    )

    children: Mapped[list[Ontology]] = relationship(
        "Ontology",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "idx_ontology_properties",
            "properties",
            postgresql_using="GIN",
            postgresql_ops={"metadata": "jsonb_path_ops"},
        ),
        Index(
            "idx_ontology_path",
            "path",
            postgresql_using="GIST",
            postgresql_ops={"metadata": "jsonb_path_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<%s id={self.id}>" % self.__class__.__name__
