from sqlalchemy import DDL, MetaData, event
from sqlalchemy.orm import declarative_base

Base = declarative_base(metadata=MetaData())

create_jsonb_array_func = DDL("""
    CREATE OR REPLACE FUNCTION jsonb_array_to_text_array(_js jsonb)
        RETURNS text[]
        LANGUAGE sql
        IMMUTABLE PARALLEL SAFE AS
    $$
    SELECT ARRAY(SELECT jsonb_array_elements_text(_js));
    $$;
""")

event.listen(Base.metadata, "before_create", create_jsonb_array_func)

from .annotation_ontology_mapping import AnnotationOntologyMapping  # noqa: E402
from .claim import Claim  # noqa: E402
from .document import Document  # noqa: E402
from .global_metadata import GlobalMetadata  # noqa: E402
from .job import Job  # noqa: E402
from .ontology import Ontology  # noqa: E402
from .precomputed_stats import PreComputedStats  # noqa: E402
from .text import Text  # noqa: E402
from .text_annotation import TextAnnotation  # noqa: E402
from .topic import Topic  # noqa: E402
from .topic_sentences import TopicSentences  # noqa: E402

__all__ = [
    "Base",
    "Document",
    "Text",
    "Topic",
    "TextAnnotation",
    "Ontology",
    "AnnotationOntologyMapping",
    "Job",
    "Claim",
    "TopicSentences",
    "PreComputedStats",
    "GlobalMetadata",
]
