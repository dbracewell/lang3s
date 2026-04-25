import logging
from typing import Annotated

from lang3s.agent import Agent, Session
from lang3s.agent.middleware import LoggingMiddleware
from lang3s.agent.strategy import ToolCallingStrategy
from lang3s.app import Application
from lang3s.llm import tools
from lang3s.nlp.claim_extractor import DocumentClaimRequest
from lang3s.services.client.redis_client import CLAIM_EXTRACT_QUEUE_NAME, RedisClient


@tools.tool(
    name="get_weather", description="Gets the weather for a city in the United States."
)
def weather(city: Annotated[str, "The city to get the current weather for in Celsius"]):
    return 45.5


class SampleApplication(Application):
    def run(self):
        # self.test_claim_extraction_workers()
        # self.test_sense_model()
        self.test_agent()

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
                if len(files) == 10:
                    break
        docs = pipeline(files)
        for doc in docs:
            for sentence in doc.text.sentences:
                print(sentence)
                for sense in sentence.annotations_of_type("senses"):
                    print(f"{sense} / {sense.value}")
                print()
            print("\n")

    def test_claim_extraction_workers(self):
        from lang3s.data.io.serialization import deserialize

        client = RedisClient()
        for doc in deserialize("/Users/ik/prj/data/news.docs"):
            client.enqueue(
                CLAIM_EXTRACT_QUEUE_NAME,
                DocumentClaimRequest(
                    documentId=doc.id, sentences=[s.text for s in doc.text.sentences]
                ).model_dump(),
            )

    def test_claim_extraction_direct(self):
        from lang3s.data.io.serialization import deserialize
        from lang3s.llm import Message
        from lang3s.nlp.claim_extractor import DocumentClaims
        from lang3s.services.client.local_llm_client import LocalLLMClient

        llm = LocalLLMClient()
        for doc in deserialize("/Users/ik/prj/data/news.docs"):
            text = doc.text.text

            response = llm.sync_generate(
                messages=[Message.user(f"Extract claims from: {text}")],
                adapter_name="claim",
                temperature=0.0,
                max_tokens=2000,
                response_model=DocumentClaims,
            )
            if response.parsed:
                for claim in response.parsed.claims:
                    print(claim)
            else:
                print(response.content)


if __name__ == "__main__":
    SampleApplication().run()
