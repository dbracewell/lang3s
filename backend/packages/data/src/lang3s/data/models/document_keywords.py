import sqlalchemy as sa
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Mapped
from sqlalchemy_utils import create_materialized_view

from . import Base
from .claim import Claim

unnested_claims = (
    select(
        Claim.document_id,
        func.unnest(Claim.keywords).label("kw"),
    )
    .distinct()
    .cte("unnested_claims")
)
valid_keywords = (
    select(
        unnested_claims.c.kw,
        func.count(distinct(unnested_claims.c.document_id)).label("cnt"),
    )
    .where(unnested_claims.c.kw != "")
    .group_by(unnested_claims.c.kw)
    .having(func.count() >= 10)
    .cte("valid_keywords")
)
selectable = select(
    unnested_claims.c.document_id,
    unnested_claims.c.kw.label("kw"),
    valid_keywords.c.cnt.label("kw_count"),
).select_from(
    unnested_claims.join(valid_keywords, unnested_claims.c.kw == valid_keywords.c.kw)
)


class DocumentKeywords(Base):
    __table__ = create_materialized_view(
        name="document_keywords",
        selectable=selectable,
        metadata=Base.metadata,
        indexes=[
            sa.Index("idx_document_keywords_document_id", "document_id"),
            sa.Index("idx_document_keywords_kw", "kw"),
            sa.Index(
                "idx_document_keywords_document_id_kw",
                "document_id",
                "kw",
                unique=True,
            ),
        ],
    )
    __mapper_args__ = {"primary_key": [__table__.c.document_id, __table__.c.kw]}
    document_id: Mapped[str]
    kw: Mapped[str]
    kw_count: Mapped[int]
