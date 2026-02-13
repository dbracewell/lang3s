from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lang3s.agent.agent import Agent
from lang3s.agent.middleware.logging_middleware import LoggingMiddleware
from lang3s.agent.session import Session
from lang3s.agent.strategy.tool_calling import ToolCallingStrategy
from lang3s.llm.messages import Message
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


@router.post("/")
async def chat(request: AgentRequest):
    agent = Agent(
        session=Session(
            initial_messages=[Message(**d) for d in request.messages],
            available_tools=[document_search, topics_search],
            middleware=[LoggingMiddleware()],
            system_message="You are a helpful assistant that answers users' questions.",
        )
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

    response = agent.sync_run(prompt, strategy=ToolCallingStrategy())
    if response.exception:
        return JSONResponse(content=str(response.exception), status_code=500)
    return AgentResponse(response=response.content[-1])
