from __future__ import annotations

import networkx as nx
import shortuuid
from pydantic import BaseModel, Field
from scipy.cluster.hierarchy import linkage
from sqlalchemy import delete

from lang3s.app import Application
from lang3s.cluster.hierarchical import ClusterNode, DivisiveKMeans
from lang3s.data.db.models import TopicsTable, TopicsTreeTable, TopicTreeTopicMapTable
from lang3s.llm import LLMClient, Message
from lang3s.nlp.claim_extractor import create_claim_request
from lang3s.nlp.metadata import AnnotationTypes
from lang3s.services.client.redis_client import CLAIM_EXTRACT_QUEUE_NAME, RedisClient
from lang3s.utils.logger import get_logger


class TopicNode(BaseModel):
    name: str
    is_leaf: bool = Field(default=False)
    children: list[TopicNode] = Field(default_factory=list)
    elements: list[str] = Field(default_factory=list)


class TopicHierarchy(BaseModel):
    root: TopicNode


import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# def build_metadata_tree(X, metadata):
#     Z = linkage(X, method="ward")
#     n_samples = len(X)
#     G = nx.Graph()
#
#     for i in range(n_samples):
#         G.add_node(i, type="leaf", data=metadata[i])
#
#     for i, row in enumerate(Z):
#         new_node_id = n_samples + i
#         child1 = int(row[0])
#         child2 = int(row[1])
#         distance = row[2]
#
#         G.add_node(new_node_id, type="internal", distance=distance)
#         G.add_edge(new_node_id, child1, weight=distance)
#         G.add_edge(new_node_id, child2, weight=distance)
#
#     return G, n_samples + len(Z) - 1
#
#
# def traverse(G, current_node, parent=None):
#     node_data = G.nodes[current_node]
#
#     if node_data["type"] == "leaf":
#         print(f"Leaf: {node_data['data']}")
#     else:
#         print(f"Node (Dist: {node_data['distance']:.2f})")
#
#     for neighbor in G.neighbors(current_node):
#         if neighbor != parent:
#             traverse(G, neighbor, current_node)
#

logger = get_logger("TEST")


class SampleApplication(Application):
    def run(self):
        # self.cluster_topics()
        import lang3s.data.db.text_database as text_db

        for s in text_db.random_sentences(1000):
            print(s)

    def cluster_topics(self):
        import lang3s.data.db.database as db

        topics = []
        topic_embs = []

        with db.get_session() as session:
            for c in session.query(TopicsTable).all():
                topics.append(c)
                topic_embs.append(c.embedding.to_numpy())
            session.expunge_all()

        dm = DivisiveKMeans(max_k=10, min_samples_leaf=2)
        dm.fit(topic_embs, topics)
        if dm.root is None:
            print("NO ROOT")
        else:
            tree_map = []
            joining_table = []
            if dm.root:
                frontier = [(None, dm.root)]
                while frontier:
                    parent_id, next_node = frontier.pop()
                    node_id = shortuuid.uuid()
                    name = "ROOT"
                    if parent_id:
                        name = generate_name(next_node)
                    tree_map.append(
                        TopicsTreeTable(
                            id=node_id,
                            parent=parent_id,  # type: ignore
                            name=name,
                            isLeaf=next_node.is_leaf,
                            splitK=next_node.k,
                        )
                    )
                    for item in next_node.items:
                        joining_table.append(
                            TopicTreeTopicMapTable(
                                nodeId=node_id,
                                topicId=item.id,
                            )
                        )
                    for child in next_node.children:
                        frontier.append((node_id, child))

                with db.get_session() as session:
                    session.execute(delete(TopicsTreeTable))
                    session.execute(delete(TopicTreeTopicMapTable))
                    session.bulk_save_objects(tree_map)
                    session.bulk_save_objects(joining_table)

        # G, root = build_metadata_tree(topic_embs, topics)
        # traverse(G, root)

    def test_sense_model(self):
        import jsonlines
        from lang3s_job_service import File

        from lang3s.pipeline import pipeline

        files = []
        with jsonlines.open("/Users/ik/prj/data/news.jsonl") as reader:
            for doc in reader:
                files.append(File.model_validate(doc))
                if len(files) == 200:
                    break
        for doc in pipeline(files, batch_size=10):
            for sentence in doc.text.sentences:
                for annotation in sentence.interleave("senses"):
                    if annotation.type == AnnotationTypes.TOKEN:
                        print(f"{annotation}\tO")
                    else:
                        isFirst = True
                        for token in annotation.tokens:
                            print(
                                f"{token}\t{'B' if isFirst else 'I'}-{annotation.value}"
                            )
                            isFirst = False
                print("\n")

    def test_claim_extraction_workers(self):
        from lang3s.data.io.serialization import deserialize

        client = RedisClient()
        count = 0
        for doc in deserialize("/Users/david/prj/data/news.docs"):
            client.enqueue(
                CLAIM_EXTRACT_QUEUE_NAME,
                create_claim_request(doc).model_dump(),
            )
            count += 1
            if count > 1001:
                break


if __name__ == "__main__":
    SampleApplication().run()
