from collections import defaultdict
from typing import Annotated, Any, Literal

from dateutil import parser
from sqlalchemy import ScalarResult, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.functions import func

from lang3s.agent import Agent
from lang3s.agent.llm import Desc, tool
from lang3s.agent.strategy import DiscoveryStrategy
from lang3s.data.db import Database, TextDatabase
from lang3s.data.db.models import (
    DocumentsTable,
    MetadataTable,
    PrecomputedStatsTable,
    TextAnnotationsTable,
    TopicsTable,
)
from lang3s.models import Embedder
from lang3s.nlp.shared_types import Metadata
from lang3s.services.service_logging import get_logger


@tool(description="Searches the database for results similar to the given query.")
def search_database(query: Annotated[str, Desc("The query to search.")]):
    text_db = TextDatabase()

    if query == "*":
        return text_db.random_sentences(500)

    if query in (
        "a",
        "the",
        "data",
        "report",
        "sports",
        "economy",
        "business",
        "computers",
        "life",
        "entertainment",
    ):
        return text_db.search(query=query, limit=5)

    embedder = Embedder()
    embedding = embedder([query]).sentence_embeddings[0]
    results = text_db.sentence_search(embedding, 0.3, limit=5)
    return results


logger = get_logger(__name__)


def generate_corpus_summary():
    logger.info("Starting to process: discovery")
    corpus_discovery = DiscoveryStrategy(
        search_tool="search_database", rounds=1, queries_per_round=3
    )
    agent = Agent(
        strategy=corpus_discovery,
        tools=[search_database],
    )
    response = agent.invoke(
        prompt="Determine the main topics of the corpus. The corpus is comprised of news articles."
    )
    logger.info("Finished discovery")
    logger.info("Starting collecting statistics")
    db = Database()
    with db.session() as session:
        stmt = select(TopicsTable).order_by(TopicsTable.support.desc()).limit(7)
        topics = session.execute(stmt).scalars().all()
        total_docs = session.scalar(
            select(func.count().label("count")).select_from(DocumentsTable)
        )
        total_sentences = session.scalar(
            select(func.count().label("count"))
            .select_from(TextAnnotationsTable)
            .where(TextAnnotationsTable.type_ == "sentence")
        )
        total_annotations = session.scalar(
            select(func.count().label("count"))
            .select_from(TextAnnotationsTable)
            .where(TextAnnotationsTable.type_ != "sentence")
        )

    topic_summary = []
    for topic in topics:
        topic_summary.append(
            {
                "name": topic.name,
                "support": topic.support,
            }
        )

    logger.info("Finished collecting statistics")
    logger.info("Saving results")
    with db.session(commit=True) as session:
        stmt = insert(PrecomputedStatsTable).values(
            {
                "name": "corpus_summary",
                "value": {
                    "corpus_summary": response.content[-1],
                    "topic_summary": topic_summary,
                    "overall_stats": {
                        "documents": total_docs,
                        "sentences": total_sentences,
                        "annotations": total_annotations,
                    },
                },
            }
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[PrecomputedStatsTable.name],
            set_={"value": stmt.excluded.value},
        )
        session.execute(stmt)
    logger.info("Finished saving results")


def is_date(value: str) -> bool:
    try:
        parser.parse(value)
        return True
    except ValueError:
        return False


def guess_metadata(
    metadata_source: Literal["document", "sentence", "annotation"],
) -> dict[str, str]:
    db = Database()

    if metadata_source == "document":
        metadata_column = DocumentsTable.metadata_
        where = text("1 = 1")
    elif metadata_source == "sentence":
        metadata_column = TextAnnotationsTable.metadata_
        where = TextAnnotationsTable.type_ == "sentence"
    else:
        metadata_column = TextAnnotationsTable.metadata_
        where = TextAnnotationsTable.type_ != "sentence"

    with db.session() as session:
        results: ScalarResult[dict[str, Any]] = session.scalars(
            select(metadata_column).where(where).limit(25000)
        )
        metadata: dict[str, set] = defaultdict(set)
        for result in results:
            for key, value in result.items():
                if isinstance(value, list):
                    if len(value) == 0 or type(value[0]).__name__ != "str":
                        continue
                    v = "str[]"
                    metadata[key].add(v)
                elif not isinstance(value, dict):
                    metadata[key].add(value)

        for ignore in Metadata:
            metadata.pop(ignore.value, None)

        if len(metadata) == 0:
            return {}

        type_info: dict[str, str] = dict()
        for key, value in metadata.items():
            if len(value) == 0:
                continue
            if len(value) == 1 and value.pop() == "str[]":
                type_info[key] = "string[]"
            elif any(isinstance(v, float) for v in value if v is not None):
                type_info[key] = "float"
            elif all(isinstance(v, int) for v in value if v is not None):
                type_info[key] = "int"
            elif all(isinstance(v, bool) for v in value if v is not None):
                type_info[key] = "boolean"
            elif all(is_date(v) for v in value if v is not None):
                type_info[key] = "date"
            elif all(isinstance(v, str) for v in value if v is not None):
                type_info[key] = "string"

    return type_info


def probe_metadata():
    values = []

    for metadata_source in ["document", "sentence", "annotation"]:
        metadata = guess_metadata(metadata_source=metadata_source)  # type:ignore
        for key, valueType in metadata.items():
            formatter = None
            if valueType == "date":
                formatter = "yyyy-MM-dd"
            elif valueType == "number":
                formatter = "2"

            values.append(
                {
                    "source": metadata_source,
                    "name": key,
                    "data_type": valueType,
                    "formatter": formatter,
                }
            )

    if not values:
        return

    with Database().session(commit=True) as session:
        session.execute(
            insert(MetadataTable)
            .values(values)
            .on_conflict_do_nothing(
                index_elements=[MetadataTable.source, MetadataTable.name]
            )
        )
