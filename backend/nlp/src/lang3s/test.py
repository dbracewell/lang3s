import json
import logging
import os.path
import sys
import time
from random import shuffle
from typing import Annotated

from jsonlines import jsonlines
from lang3s_job_service import File
from pydantic import BaseModel
from transformers import Pipeline

from lang3s.agent import Agent, Session
from lang3s.agent.middleware import LoggingMiddleware
from lang3s.agent.strategy import ToolCallingStrategy
from lang3s.app import Application
from lang3s.config import Config, config
from lang3s.data.db.models import ClaimsTable
from lang3s.data.io.serialization import deserialize
from lang3s.llm import Message, tools
from lang3s.llm.client import LoRaClient
from lang3s.nlp.claim_extractor import ClaimList, create_claim_request
from lang3s.nlp.metadata import AnnotationTypes
from lang3s.parallel.core import Engine
from lang3s.parallel.manager import TaskManager
from lang3s.parallel.monitor import ThreadMonitor
from lang3s.services.client.redis_client import CLAIM_EXTRACT_QUEUE_NAME, RedisClient


@tools.tool(
    name="get_weather", description="Gets the weather for a city in the United States."
)
def weather(city: Annotated[str, "The city to get the current weather for in Celsius"]):
    return 45.5


class Joke(BaseModel):
    text: str


class SampleApplication(Application):
    def run(self):
        # self.test_llm()
        self.test_claim_extraction_workers()
        return
        # self.test_sense_model()
        # self.test_agent()
        # self.test_claim_classification()
        # self.create_base_corpora()
        # self.cluster_claims()
        client = LoRaClient()
        prompt = """Extract claims from: Golden rule boost for Chancellor Chancellor Gordon Brown has been given a £2.1bn boost in his attempts to meet his golden economic rule, which allows him to borrow only for investment. The extra leeway came after the Office for National Statistics said it had been measuring road expenditure data wrongly over the past five years. It comes just weeks ahead of the Budget and an expected general election. Shadow chancellor Oliver Letwin said: "At best the timing of these changes is very convenient for the government." A review by the ONS found it had made a mistake by "double counting" some spending on roads since 1998/9. Correcting the error would mean reducing current expenditure and increasing net investment, thus helping Mr Brown to meet his "golden rule" of borrowing only to invest over the economic cycle. Economists speculated that it might also allow for some vote-catching measures in the Budget. The changes by the ONS increase the current budget measure for the past five years by £2.1bn in total. Mr Letwin said: "This is a very murky area... There will inevitably be suspicions that the figures are being fiddled." The Conservatives also said Mr Brown would still be forced to raise taxes after the general election to fill an annual £10.5bn "black hole" in the nation's coffers. But the Treasury said there would be no relaxation of economic discipline and the golden rule would be met even without the data revisions. In January the independent Institute for Fiscal Studies (IFS) said Mr Brown would need to raise taxes to get public finances onto the track predicted in last year's Budget. It also said the government might narrowly miss its "golden rule" if the current economic cycle ended in 2005/06. After the ONS announcement, economists said there could also be a proportionate boost to the current budget in 2004/05 of about £400m. "None of this changes the big picture of a dramatic deterioration in the overall fiscal position over the last four or five years," said Jonathan Loynes, chief UK economist at Capital Economics. "Accordingly, it seems very likely that some form of fiscal consolidation will be required in due course."""

        start = time.perf_counter()
        r = client.sync_chat_completion_last_event(
            messages=[Message.user(prompt)],
            temperature=0,
        )
        end = time.perf_counter()
        print(r.content)
        print(f"{end - start:0.2f}")

    def extract_svo(self, doc):
        svo_triples = []
        for token in doc:
            # We look for a verb (the head of the triple)
            if token.pos_ == "VERB":
                subj = ""
                obj = ""
                # Look for the subject and object among the verb's children
                for child in token.children:
                    if child.dep_ in ("nsubj", "nsubjpass"):
                        subj = " ".join([t.text for t in child.subtree])
                    if child.dep_ in ("dobj", "obj", "pobj"):
                        obj = " ".join([t.text for t in child.subtree])

                if subj and obj:
                    svo_triples.append((subj, token.lemma_, obj))
        return svo_triples

    # Example usage:
    # doc = nlp("The Bank of England's rate-setting body voted to leave interest rates unchanged.")
    # print(extract_svo(doc))

    def cluster_claims(self):
        import lang3s.data.db.database as db
        from lang3s.cluster.offline import DefaultOfflineClusterer

        claims = []
        embeddings = []

        with db.get_session() as session:
            for c in session.query(ClaimsTable).all():
                claims.append(c.claim)
                embeddings.append(c.embedding.to_numpy())

        clusterer = DefaultOfflineClusterer(
            min_cluster_size=2,
            metric="euclidean",
            clustering_algorithm="agglomerative",
            distance_threshold=1.0,
        )
        clusters = clusterer.fit(claims, embeddings)
        print(len(clusters))
        for cluster in clusters:
            shuffle(cluster.items)
            print("\n".join(cluster.items[:5]))
            print()

    def create_base_corpora(self):
        with jsonlines.open("/Users/ik/prj/data/base_corpus.jsonl", "w") as writer:
            # reddit
            with open("/Users/ik/prj/data/reddit_style_corpus.json") as reader:
                all_docs = json.load(reader)
                for doc in all_docs:
                    writer.write(
                        File(
                            content=doc["text"],
                            docId=doc["id"],
                            metadata={"source": doc["source"]},
                        ).model_dump()
                    )

            # news
            with jsonlines.open("/Users/ik/prj/data/news.jsonl") as reader:
                for doc in reader:
                    writer.write(doc)

            for doc in deserialize("/Users/ik/prj/data/kant.docs"):
                writer.write(
                    File(
                        content=doc.text.text,
                        docId=doc.id,
                        mime_type="text/plain",
                        metadata=doc.metadata,
                    ).model_dump()
                )

    def get_semantic_overlap_chunks(
        self,
        sentences: list[str],
        window_size=5,
        overlap=2,
    ):
        chunks = []
        step = window_size - overlap
        if step <= 0:
            step = 1

        for i in range(0, len(sentences), step):
            window = sentences[i : i + window_size]
            chunk_text = " ".join(window)
            chunks.append(chunk_text)
            if i + window_size >= len(sentences):
                break

        return chunks

    def test_claim_classification(self):
        client = LoRaClient()
        window_size = 10
        overlap = 2
        for doc in deserialize(os.path.expanduser("~/prj/data/kant.docs")):
            start = time.perf_counter()
            sentences = [s.text for s in doc.text.sentences]
            chunks = self.get_semantic_overlap_chunks(sentences, window_size, overlap)
            combined = []
            for chunk in chunks:
                prompt = f"Extract claims from: {chunk}"
                response = client.sync_chat_completion_last_event(
                    messages=[Message.user(prompt)],
                    temperature=0,
                )
                try:
                    rc = json.loads(response.content, strict=False)
                    combined.extend(rc)
                except json.decoder.JSONDecodeError as e:
                    print(f"Error {e}", file=sys.stderr)
            end = time.perf_counter()
            print(f"{len(chunks)}: {(end - start):.2f}", file=sys.stderr)
            print(json.dumps(combined))

    def test_agent(self):
        agent = Agent(
            session=Session(
                available_tools=[weather],
                middleware=[LoggingMiddleware(level=logging.DEBUG)],
            )
        )
        result = agent.sync_run(
            "What's the weather in Orlando, FL",
            strategy=ToolCallingStrategy(),
        )
        print(result)

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
