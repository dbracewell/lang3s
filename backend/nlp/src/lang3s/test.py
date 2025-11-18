import math
from typing import List

from pydantic.main import BaseModel

from lang3s.agent import Agent
from lang3s.agent.steps.dispatch import PlanRouterStep
from lang3s.agent.steps.loops import LoopStep
from lang3s.agent.steps.planning import PlanStep
from lang3s.db import TextDatabase
from lang3s.models import Embedder
from lang3s.models.llm import global_tool_registry
from .agent.shared_types import ExampleList, RetrievalResult
from .logger import initialize_logger

initialize_logger()


class Response(BaseModel):
    category: str
    text: str


class ResponseList(BaseModel):
    responses: List[Response]


class Extraction(BaseModel):
    entity: str
    label: str


class ExtractionList(BaseModel):
    extractions: List[Extraction]


class SearchArgs(BaseModel):
    query: str


class SearchResponse(BaseModel):
    results: List[str]


@global_tool_registry.tool(
    args_model=SearchArgs,
    description="Searches the database for relevant information given a query",
    result_model=SearchResponse,
)
def search(query: str) -> SearchResponse:
    embedder = Embedder()
    textdb = TextDatabase()
    max_difference = embedder.dimensions - math.floor(embedder.dimensions * 0.2)
    e = embedder([query]).sentence_embeddings[0]
    r = textdb.sentence_search(e, max_difference=max_difference, limit=10)
    if len(r) == 0:
        r = textdb.search(query, limit=10)
    return SearchResponse(results=r)


def retriever(query: str) -> List[RetrievalResult]:
    results = search(query).results
    return [RetrievalResult(result=r, score=1) for r in results]


agent = Agent()
agent.add_step(LoopStep(max_loops=1,
                        steps=[
                            PlanStep(available_tools=["search"], history=10),
                            PlanRouterStep(retriever=retriever),
                        ]))
# agent.add_step(AutoToolStep(max_retries=3))
# agent.add_step(GenerationStep(response_model=ExtractionList,
#                               name="Extractor",
#                               prompt="Extract all entities from each of the example sentences given."))

result = agent.run(
    system_message="Do not output <think> tags, chain-of-thought, or hidden reasoning text. Only give the final answer in plain text.",
    # user_message="I know nothing about this corpus. Please do deep research as a series of search and analyze and finally summarization to tell me the main topics in this corpus. You will need to generate queries that are likely to return results from a general corpus. Your queries should be simple keywords or combination of keywords. Please be robust in your searching to make sure you cover all possible topics. Your final summary should be 3 - 4 paragraphs. You have 10 iterations of planning and running an action to come up with your summary.",
    user_message="Generate a 1000 example sentences discussing the topic sports injuries."
)

all_examples: List[ExampleList] = result.steps["ExampleGeneratorStep"]
ex = []
for example in all_examples:
    ex.extend(example.examples)

for example in ex:
    print(example)
# print(result.steps.get("SummarizationStep"))
# print(result.steps.get("AnalyzeStep"))
