from collections import defaultdict
from typing import Annotated, Any, Literal

from pydantic import BaseModel
from sqlalchemy import ScalarResult, select
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


def generate_corpus_summary():
    print("Starting to process: discovery")
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

    with db.session() as session:
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


class MetadataEntry(BaseModel):
    name: str
    valueType: Literal["string", "string[]", "number", "date"]


class MetadataProbe(BaseModel):
    metadata: list[MetadataEntry]


def probe_metadata():
    db = Database()
    with db.session() as session:
        results: ScalarResult[dict[str, Any]] = session.scalars(
            select(DocumentsTable.metadata_).limit(5000)
        )
        metadata: dict[str, set] = defaultdict(set)
        for result in results:
            for key, value in result.items():
                if isinstance(value, list) or isinstance(value, dict):
                    if isinstance(value, list):
                        if len(value) == 0:
                            continue
                        v = f"{type(value[0]).__name__}[]"
                    else:
                        v = f"dict"
                    metadata[key].add(v)
                else:
                    metadata[key].add(value)

        metadata.pop("path", None)
        metadata.pop("mime-type", None)
        metadata.pop("title", None)
        metadata.pop("language", None)
        if len(metadata) == 0:
            return

        agent = Agent(output_format=MetadataProbe)
        response = agent.invoke(
            prompt=f"""
        Give the following metadata identify the type of the value for each metadata key.
        {"\n".join([f"{key} = {list(value)[:5]}" for key, value in metadata.items()])}
        /no_think
        """,
        )

    if not response.parsed:
        return

    with db.session() as session:
        type_info: MetadataProbe = response.parsed[0]
        values = []
        for entry in type_info.metadata:
            formatter = None
            if entry.valueType == "date":
                formatter = "yyyy-MM-dd"
            values.append(
                MetadataTable(
                    source="document",
                    name=entry.name,
                    dataType=entry.valueType,
                    formatter=formatter,
                )
            )
        insert(MetadataTable).values(values).on_conflict_do_nothing(
            index_elements=[MetadataTable.source, MetadataTable.name]
        )
