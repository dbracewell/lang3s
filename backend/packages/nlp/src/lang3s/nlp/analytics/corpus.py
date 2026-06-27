from collections import defaultdict
from typing import Any, Literal

from dateutil import parser
from sqlalchemy import ScalarResult, select, text
from sqlalchemy.dialects.postgresql import insert

from lang3s.core.logger import get_logger
from lang3s.data.db import async_db_session
from lang3s.data.models import Document, GlobalMetadata, TextAnnotation
from lang3s.data.schemas import Metadata


async def corpus_summarization():
    logger = get_logger("GENERATE_CORPUS_SUMMARY")
    logger.info("Starting to process: discovery")
    # corpus_discovery = DiscoveryStrategy(
    #     search_tool="search_database",
    #     rounds=2,
    #     queries_per_round=3,
    # )
    # agent = Agent(
    #     session=Session(
    #         available_tools=[search_database],
    #     )
    # )
    #
    # response = agent.sync_run(
    #     task="Determine the main topics of the corpus. The corpus is comprised of news articles.",
    #     strategy=corpus_discovery,
    # )
    # logger.info("Finished discovery")
    # logger.info("Starting collecting statistics")
    # with db.get_session() as session:
    #     stmt = select(TopicsTable).order_by(TopicsTable.support.desc()).limit(7)
    #     topics = session.execute(stmt).scalars().all()
    #     total_docs = session.scalar(
    #         select(func.count().label("count")).select_from(DocumentsTable)
    #     )
    #     total_sentences = session.scalar(
    #         select(func.count().label("count"))
    #         .select_from(TextAnnotationsTable)
    #         .where(TextAnnotationsTable.type_ == "sentence")
    #     )
    #     total_annotations = session.scalar(
    #         select(func.count().label("count"))
    #         .select_from(TextAnnotationsTable)
    #         .where(TextAnnotationsTable.type_ != "sentence")
    #     )
    #
    #     topic_summary = []
    #     for topic in topics:
    #         topic_summary.append(
    #             {
    #                 "name": topic.name,
    #                 "support": topic.support,
    #             }
    #         )

    logger.info("Finished collecting statistics")
    logger.info("Saving results")
    # with db.get_session() as session:
    #     if response.exception:
    #         response.print_exception()
    #         return
    #     stmt = insert(PrecomputedStatsTable).values(
    #         {
    #             "name": "corpus_summary",
    #             "value": {
    #                 "corpus_summary": response.content[-1],
    #                 "topic_summary": topic_summary,
    #                 "overall_stats": {
    #                     "documents": total_docs,
    #                     "sentences": total_sentences,
    #                     "annotations": total_annotations,
    #                 },
    #             },
    #         }
    #     )
    #     stmt = stmt.on_conflict_do_update(
    #         index_elements=[PrecomputedStatsTable.name],
    #         set_={"value": stmt.excluded.value},
    #     )
    #     session.execute(stmt)
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
