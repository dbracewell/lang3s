import sqlalchemy as sa
from sqlalchemy import Numeric, cast, func, literal, select
from sqlalchemy.orm import Mapped
from sqlalchemy_utils import create_materialized_view

from . import Base
from .document import Document
from .document_keywords import DocumentKeywords

doc_freq_keywords = select(DocumentKeywords).cte("doc_freq_keywords")
k1 = doc_freq_keywords.alias("k1")
k2 = doc_freq_keywords.alias("k2")
global_stats = (
    select(func.count().label("total_docs")).select_from(Document).cte("global_stats")
)
paired_counts = (
    select(
        k1.c.kw.label("kw1_kw"),
        k1.c.kw_count.label("kw1_cnt"),
        k2.c.kw.label("kw2_kw"),
        k2.c.kw_count.label("kw2_cnt"),
        func.count().label("joint_cnt"),
    )
    .select_from(
        k1.join(k2, (k1.c.document_id == k2.c.document_id) & (k1.c.kw < k2.c.kw))
    )
    .group_by(k1.c.kw, k1.c.kw_count, k2.c.kw, k2.c.kw_count)
    .having(func.count() >= 10)
    .cte("paired_counts")
)
pmi_expr = func.log(
    cast(2.0, Numeric),
    (cast(paired_counts.c.joint_cnt, Numeric) * global_stats.c.total_docs)
    / (paired_counts.c.kw1_cnt * paired_counts.c.kw2_cnt),
)
selectable = (
    select(
        paired_counts.c.kw1_kw,
        paired_counts.c.kw1_cnt,
        paired_counts.c.kw2_kw,
        paired_counts.c.kw2_cnt,
        paired_counts.c.joint_cnt,
        pmi_expr.label("pmi_score"),
    )
    .select_from(paired_counts.join(global_stats, literal(True)))
    .where(pmi_expr > 2.0)
)


class KeywordSimilarities(Base):
    __table__ = create_materialized_view(
        name="keyword_similarities",
        selectable=selectable,
        metadata=Base.metadata,
        indexes=[
            sa.Index("idx_keyword_similarities_kw1", "kw1_kw"),
            sa.Index("idx_keyword_similarities_kw2", "kw2_kw"),
            sa.Index(
                "idx_keyword_similarities_kw1_kw2",
                "kw1_kw",
                "kw2_kw",
                unique=True,
            ),
        ],
    )
    __mapper_args__ = {"primary_key": [__table__.c.kw1_kw, __table__.c.kw2_kw]}
    kw1_kw: Mapped[str]
    kw2_kw: Mapped[str]
    kw1_cnt: Mapped[int]
    kw2_cnt: Mapped[int]
    joint_cnt: Mapped[int]
    pmi_score: Mapped[float]
