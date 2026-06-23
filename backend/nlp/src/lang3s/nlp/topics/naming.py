import textwrap
from logging import Logger

import numpy as np
from joblib import Parallel, delayed
from sklearn.feature_extraction.text import TfidfVectorizer

from lang3s.cluster.hierarchical import ClusterNode
from lang3s.llm import LLMClient, Message
from lang3s.nlp.topics.topic import Topic, TopicList
from lang3s.utils import flatten, try_catch


def label_topics(topics: TopicList, logger: Logger) -> None:
    _generate_topic_keywords(topics, logger)
    with try_catch(on_error=lambda e: logger.error(e)):
        parallel: Parallel
        with Parallel(
            n_jobs=-1,
            prefer="threads",
            mmap_mode="shared",
        ) as parallel:
            labels = parallel(
                [delayed(_generate_topic_name_from_keywords)(v) for v in topics]
            )
            for topic, label in zip(topics, labels):
                topic.name = label


def _generate_topic_keywords(topics: TopicList, logger: Logger) -> None:
    logger.info("Labelling Topics...")
    vectorizer = TfidfVectorizer()
    text = [[s.clean for s in topic.get_sentences()] for topic in topics]
    vectorizer.fit(flatten(text))
    to_name = []
    for sentences, topic in zip(text, topics):
        if topic.is_fixed or not topic.last_updated:
            logger.info("SKIPPING: ", topic.id)
            continue

        to_name.append(topic)
        X = vectorizer.transform(sentences)
        tfidf_scores = np.asarray(X.mean(axis=0)).flatten()  # type: ignore
        words = np.array(vectorizer.get_feature_names_out())
        topic.name = ", ".join(words[np.argsort(tfidf_scores)[-5:]][::-1])


def _generate_topic_name_from_keywords(topic: Topic) -> str:
    client = LLMClient()
    sentences = [t.text for t in topic.get_sentences(limit=100, randomize=True)]
    prompt = textwrap.dedent(f"""
                    Given the following sentences and list of keywords generate a short phrase that defines the topic.
                    Make the phrase generic and not specific to ONE keyword or sentence it should be generic enough to cover the entier set of sentences and keywords.
                    Give no explanation or reasoning for your answer only the answer and in plain text NO MARKUP.

                    Keywords:
                    {topic.name}

                    Sentences:
                    {"\n".join(sentences)}
                """).strip()
    response = client.sync_chat_completion_last_event([Message.user(prompt)])
    if response.exception or not response.content:
        return topic.name
    return response.content.title()


def generate_cluster_node_name(node: ClusterNode):
    topics = [item.name for item in node.items]
    client = LLMClient()
    response = client.sync_chat_completion_last_event(
        messages=[
            Message.user(
                f"Generate a concise name for a cluster of topics with the following names: {', '.join(topics)}\n\nOutput results in plain text with no explanation or formatting. Only output the name."
            )
        ]
    )
    if response.content:
        return response.content.strip('*"').strip()
    return f"Cluster of {len(topics)} topics"
