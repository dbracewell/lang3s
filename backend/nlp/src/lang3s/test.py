import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

import sqlalchemy
import umap
from pydantic import BaseModel
from sklearn.cluster._hdbscan import hdbscan
from sqlalchemy import Boolean, cast, distinct, func, select, text
from tqdm import tqdm

import lang3s.data.db.database as db
import lang3s.data.db.text_database as text_db
from lang3s import config
from lang3s.agent.ref.agent import Agent
from lang3s.agent.ref.events import AgentEvent, AgentEventType
from lang3s.agent.ref.session import Middleware, Session, State
from lang3s.agent.ref.strategy.iterative import IterativeStrategy
from lang3s.agent.ref.strategy.one_shot import OneShotStrategy
from lang3s.app import Application
from lang3s.data.db.database import get_session
from lang3s.data.db.models import (
    ClaimsTable,
    KeywordsTable,
    TextAnnotationsTable,
    TopicsTable,
)
from lang3s.llm.client import LLMClient
from lang3s.llm.events import LLMEventType
from lang3s.llm.messages import Message, format_messages_for_model
from lang3s.llm.tools import Desc, tool
from lang3s.models import Embedder
from lang3s.nlp.topics import Lang3sTopicModel
from lang3s.nlp.topics.model import topic_model


@tool(description="Searches the database for results similar to the given query.")
def search_database(query: Annotated[str, Desc("The query to search.")]):
    if query == "*":
        results = text_db.random_sentences(25)

    elif query in (
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
        results = text_db.fts_sentence_search(query=query, limit=5)
    else:
        embedder = Embedder()
        embedding = embedder([query]).sentence_embeddings[0]
        results = text_db.semantic_sentence_search(embedding, 0.3, limit=5)

    return results


class LoggingMiddleware(Middleware):
    def __call__(self, event: AgentEvent, state: State) -> None:
        if event.type == AgentEventType.TEXT_DELTA:
            return
        total_chars = sum(
            len(msg["content"])
            for msg in format_messages_for_model(state.messages)
            if "content" in msg
        )
        print(
            f"{event.type.value}: Total Tokens: {state.total_token_count}, Total Chars: {total_chars}"
        )


class Examples(BaseModel):
    examples: list[str]


def get_topic_count(topic_centroid):
    # It is critical to use a fresh session or connection per thread
    with get_session() as session:
        # 1. Disable JIT for this thread's connection
        session.execute(text("SET jit = off;"))
        session.execute(text("SET hnsw.ef_search = 100;"))

        # 2. Run your optimized HNSW query
        stmt = select(func.count()).select_from(
            select(TextAnnotationsTable.id)
            .where(
                TextAnnotationsTable.type_ == "sentence",
                cast(TextAnnotationsTable.metadata_["is_stopword"], Boolean).is_(False),
                TextAnnotationsTable.embedding.cosine_distance(topic_centroid) < 0.35,
            )
            .order_by(TextAnnotationsTable.embedding.cosine_distance(topic_centroid))
            .limit(25000)
            .subquery()
        )
        return session.scalar(stmt)


class Test(Application):
    def keyword_clustering(self):
        stmt = select(ClaimsTable).execution_options(yield_per=100)
        keywords = []
        embeddings = []
        with db.get_session() as session:
            keyword: ClaimsTable
            for keyword in session.execute(stmt).scalars():
                keywords.append(keyword.content)
                embeddings.append(keyword.embedding.to_numpy())

        reducer = umap.UMAP(
            n_neighbors=15,
            n_components=32,
            metric="cosine",
        )
        reduced = reducer.fit_transform(embeddings)

        clusterer = hdbscan.HDBSCAN(min_cluster_size=20, metric="cosine")
        labels = clusterer.fit_predict(reduced)

        clusters = defaultdict(list)
        for label, keyword in zip(labels, keywords):
            if label == -1:
                continue
            clusters[label].append(keyword)

        client = LLMClient()
        for label, keywords in clusters.items():
            cnt = Counter(keywords)
            topn = [c for c, v in cnt.most_common(50)]
            prompt = f"""
                Given the following list of keywords come up with a short noun phrase no more than four words describing the concept/topic. Give no explanation or reasoning for your answer only the answer and in plain text NO MARKUP.
                
                Keywords:
                {"\n".join(topn)}
            """
            response = client.sync_chat_completion_last_event([Message.user(prompt)])
            if response.exception:
                print(response.exception)
            else:
                print(response.content, topn)

    def run(self):
        topic_model = Lang3sTopicModel()
        topics = [
            topic.embedding for topic in topic_model.topics
        ]  # your list of 300 centroids

        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(get_topic_count, topics))
        end = time.perf_counter()
        print(f"{end - start:2f} seconds")
        # for r, t in zip(results, topic_model.topics):
        #     print(f"{r}: {t.name}")

        return
        agent = Agent(
            Session(available_tools=[search_database], middleware=[LoggingMiddleware()])
        )
        r = agent.sync_run(
            task="Generate example sentences that talk about cats and their lifes. Do not repeat sentences.",
            strategy=IterativeStrategy[Examples](
                iteration_task="Generate 5 example sentences about cats.",
                substrategy=OneShotStrategy[Examples](
                    temperature=23, response_model=Examples
                ),
                iterations=2,
            ),
        )
        if r.exception:
            print(r.exception)
            traceback.print_tb(r.exception.__traceback__)
            traceback.print_tb(r.exception.__cause__.__traceback__)
        else:
            for ex in r.parsed:
                for e in ex.examples:
                    print(e)


if __name__ == "__main__":
    Test.from_cli().run()
