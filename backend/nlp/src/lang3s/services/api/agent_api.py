import json
from typing import Annotated, Any, Dict, List, Optional

import redis
import shortuuid
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lang3s import config
from lang3s.agent import Agent, LoggingMiddleware, PlanningStrategy
from lang3s.agent.llm import Desc, tool
from lang3s.agent.middleware import NotificationMiddleware
from lang3s.agent.strategy import DiscoveryStrategy
from lang3s.data.db import TextDatabase
from lang3s.models import Embedder
from lang3s.services.api.agent_tools import document_search, topics_search

router = APIRouter(
    prefix="/agents",
    tags=["agents"],
    responses={404: {"description": "Not found"}},
)


class AgentRequest(BaseModel):
    userId: str
    prompt: str
    messages: List[Dict[str, Any]]
    context: Optional[str] = None


class AgentResponse(BaseModel):
    response: str


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


corpus_discovery = DiscoveryStrategy(
    search_tool="search_database", rounds=1, queries_per_round=3
)


def process_agent_response(userId: str):
    print("Starting to process: discovery")
    chatId = shortuuid.uuid()
    agent = Agent(
        strategy=corpus_discovery,
        tools=[search_database],
        middleware=[
            NotificationMiddleware(
                userId=userId,
                prompt="Determine the main topics of the corpus. The corpus is comprised of news articles.",
                chatId=chatId,
            )
        ],
    )
    response = agent.invoke(
        prompt="Determine the main topics of the corpus. The corpus is comprised of news articles."
    )
    redis_client = redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        decode_responses=True,
    )
    redis_client.publish(
        "events",
        json.dumps(
            {
                "type": "agent:update",
                "userid": userId,
                "payload": {
                    "id": chatId,
                    "progress": 1,
                    "prompt": "Determine the main topics of the corpus. The corpus is comprised of news articles.",
                    "response": "\n".join(response.content),
                },
            }
        ),
    )


@router.post("/discover", response_model=AgentResponse)
async def agent(request: AgentRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        process_agent_response,
        request.userId,
    )
    return AgentResponse(response="\n".join("Started"))


@router.post("/")
async def chat(request: AgentRequest):
    agent = Agent(
        strategy=PlanningStrategy(),
        tools=[document_search, topics_search],
        middleware=[LoggingMiddleware()],
        system_message="You are a helpful assistant that answers users' questions.",
    )
    prompt = f"""
    Using the supplied context (also referred to as a document). Do NOT provide any other information outside of the context or tools unless explicitly asked for by the user.

    # Formatting Rules
    - When you reference a specific document from the context, you MUST create a Markdown link.
    - Links to documents MUST be in the format: [Document Title](/documents/<documentId>)
    - Do not use absolute URLs (e.g., http://localhost/...). Use relative paths only.
    - Example: "As seen in [Project Alpha](/documents/doc_101), the timeline is strict."
    - Links to topics MUST be in the format: [Topic Name](/analytics/topics/<topicId>)
    - Do not use absolute URLs (e.g., http://localhost/...). Use relative paths only.
    - Example: "Shown in the topic [Banking Topic](/topics/topic_101)."

    TASK:
    {request.prompt}

    CONTEXT:
    {request.context}
    """
    response = await agent.async_invoke(prompt, messages=request.messages)
    if not response.success:
        return JSONResponse(content=str(response.exception), status_code=500)
    print(response.content[-1])
    return AgentResponse(response=response.content[-1])
