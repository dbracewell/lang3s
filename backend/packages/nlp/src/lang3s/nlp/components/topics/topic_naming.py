import textwrap
from logging import Logger

import numpy as np
from more_itertools import flatten
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm.asyncio import tqdm_asyncio

from lang3s.agent.llm import LLMClient, Message
from lang3s.core.exceptions import try_catch
from lang3s.core.parallel import AsyncManager, Event
from lang3s.data.db import async_db_session
from lang3s.data.repositories.text_repository import TextRepository
from lang3s.ml.cluster import ClusterNode

from .schemas import Topic, TopicCollection


async def label_topics(
    topics: TopicCollection,
    session: AsyncSession,
    logger: Logger,
) -> None:
    await _generate_topic_keywords(topics, session)
    with try_catch(on_error=lambda e: logger.error(e)):
        async with AsyncManager(workers=10) as manager:
            queue = manager.create_queue()
            for topic in topics:
                queue.put(Event(payload=topic))
            queue.stop()
            async for result in tqdm_asyncio(
                manager.imap(
                    _generate_topic_name_from_keywords,
                    queue,
                ),
                total=len(topics),
            ):
                if result.payload:
                    pass
    print("Completed naming topics")


async def _generate_topic_keywords(
    topics: TopicCollection,
    session: AsyncSession,
) -> None:
    vectorizer = TfidfVectorizer()
    repository = TextRepository(session)
    text = [
        [
            s.cleaned
            for s in await repository.get_semantically_similar_sentences(
                topic.embedding,
                limit=500,
            )
        ]
        for topic in topics
    ]
    vectorizer.fit(flatten(text))
    to_name = []
    for sentences, topic in zip(text, topics):
        if topic.is_fixed or not topic.last_updated:
            continue

        to_name.append(topic)
        X = vectorizer.transform(sentences)
        tfidf_scores = np.asarray(X.mean(axis=0)).flatten()  # type: ignore
        words = np.array(vectorizer.get_feature_names_out())
        topic.name = ", ".join(words[np.argsort(tfidf_scores)[-5:]][::-1])


async def _generate_topic_name_from_keywords(event: Event[Topic]) -> Event[Topic]:
    client = LLMClient()
    topic: Topic = event.payload  # type: ignore
    async with async_db_session() as session:
        r = await TextRepository(session).get_semantically_similar_sentences(
            limit=100,
            embedding=topic.embedding,  # type: ignore
            min_similarity=0.35,
            randomize=True,
        )
        sentences = [t.content for t in r]
    prompt = textwrap.dedent(f"""
                    Given the following sentences and list of keywords generate a short phrase that defines the topic.
                    Make the phrase generic and not specific to ONE keyword or sentence it should be generic enough 
                    to cover the entier set of sentences and keywords.
                    Give no explanation or reasoning for your answer only the answer and in plain text NO MARKUP.

                    Keywords:
                    {topic.name}

                    Sentences:
                    {"\n".join(sentences)}
                """).strip()  # noqa: E501
    response = await client.chat_last_event([Message.user(prompt)])
    if response.exception or not response.content:
        return Event(payload=topic)
    topic.name = response.content.title()
    return Event(payload=topic)


async def generate_cluster_node_name(node: ClusterNode):
    topics = [item.name for item in node.items]
    client = LLMClient()
    response = await client.chat_last_event(
        messages=[
            Message.user(
                f"Generate a concise name for a cluster of topics with the following names: {', '.join(topics)}\n\nOutput results in plain text with no explanation or formatting. Only output the name."  # noqa: E501
            )
        ]
    )
    if response.content:
        return response.content.strip('*"').strip()
    return f"Cluster of {len(topics)} topics"
