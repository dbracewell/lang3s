from collections import defaultdict
from typing import Annotated, Any, Literal

from dateutil import parser
from sqlalchemy import ScalarResult, func, select, text
from sqlalchemy.dialects.postgresql import insert

from lang3s.agent import Agent, Session
from lang3s.agent.strategy import DiscoveryStrategy
from lang3s.core.logger import get_logger
from lang3s.data.db import async_db_session
from lang3s.data.models import (
    Document,
    GlobalMetadata,
    PreComputedStats,
    TextAnnotation,
    Topic,
)
from lang3s.data.repositories.text_repository import TextRepository
from lang3s.data.schemas import Metadata
from lang3s.llm import ArgDesc, tool
from lang3s.nlp import Embedder


@tool(description="Searches the database for results similar to the given query.")
async def search_database(query: Annotated[str, ArgDesc("The query to search.")]):
    if query == "*":
        async with async_db_session() as session:
            return [
                a.content
                for a in await TextRepository(session).get_random_sentences(50)
            ]

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
        async with async_db_session() as session:
            return [
                a.content
                for a in await TextRepository(session).full_text_sentence_search(
                    query=query,
                    limit=50,
                )
            ]

    embedder = Embedder()
    embedding = embedder([query]).sentence_embeddings[0]
    async with async_db_session() as session:
        return [
            a.content
            for a in await TextRepository(session).get_semantically_similar_sentences(
                embedding,
                limit=10,
                min_similarity=0.3,
            )
        ]


async def corpus_summarization():
    logger = get_logger("GENERATE_CORPUS_SUMMARY")
    logger.info("Starting to process: discovery")
    corpus_discovery = DiscoveryStrategy(
        search_tool="search_database",
        rounds=7,
        queries_per_round=3,
        allow_random_search=True,
    )
    agent = Agent(
        session=Session(
            available_tools=[search_database],
        )
    )

    response = await agent.run(
        task="Determine the main topics of the corpus. "
        "The corpus is comprised of news articles.",
        strategy=corpus_discovery,
    )
    logger.info("Finished discovery")

    logger.info("Starting collecting statistics")
    async with async_db_session() as session:
        stmt = select(Topic).order_by(Topic.document_count.desc()).limit(7)
        topics = (await session.scalars(stmt)).all()
        total_docs = await session.scalar(
            select(func.count().label("count")).select_from(Document)
        )
        total_sentences = await session.scalar(
            select(func.count().label("count"))
            .select_from(TextAnnotation)
            .where(TextAnnotation.type_ == "sentence")
        )
        total_annotations = await session.scalar(
            select(func.count().label("count"))
            .select_from(TextAnnotation)
            .where(TextAnnotation.type_ != "sentence")
        )

        topic_summary = []
        for topic in topics:
            topic_summary.append(
                {
                    "name": topic.name,
                    "support": topic.document_count,
                }
            )

    logger.info("Finished collecting statistics")
    logger.info("Saving results")
    async with async_db_session() as session:
        if response.exception:
            print(response.exception)
            return
        stmt = insert(PreComputedStats).values(
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
            index_elements=[PreComputedStats.name],
            set_={"value": stmt.excluded.value},
        )
        await session.execute(stmt)
        await session.commit()
    logger.info("Finished saving results")


def is_date(value: str) -> bool:
    try:
        parser.parse(value)
        return True
    except ValueError:
        return False


async def _guess_metadata(
    metadata_source: Literal["document", "sentence", "annotation"],
) -> dict[str, str]:
    if metadata_source == "document":
        metadata_column = Document.metadata_json
        where = text("1 = 1")
    elif metadata_source == "sentence":
        metadata_column = TextAnnotation.metadata_json
        where = TextAnnotation.type_ == "sentence"
    else:
        metadata_column = TextAnnotation.metadata_json
        where = TextAnnotation.type_ != "sentence"

    async with async_db_session() as session:
        results: ScalarResult[dict[str, Any]] = await session.scalars(
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


async def probe_metadata():
    values = []

    for metadata_source in ["document", "sentence", "annotation"]:
        metadata = await _guess_metadata(metadata_source=metadata_source)  # type:ignore
        for key, valueType in metadata.items():
            formatter = None
            if valueType == "date":
                formatter = "%Y-%m-%d"
            elif valueType == "float":
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

    async with async_db_session() as session:
        stmt = insert(GlobalMetadata).values(values)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[
                GlobalMetadata.source,
                GlobalMetadata.name,
            ]
        )
        await session.execute(stmt)
