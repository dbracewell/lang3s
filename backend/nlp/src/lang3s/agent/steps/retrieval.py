from lang3s.agent.shared_types import AgentStep, StepResult
from typing import Callable, List
import asyncio

from pydantic.main import BaseModel
from .planning import QueryPlan


class RetrievalResult(BaseModel):
    result: str
    score: float

    def __eq__(self, other):
        return self.result == other.result

    def __hash__(self):
        return hash(self.result)


class RetrievalStep(AgentStep):
    """
    Calls a retriever and injects retrieved documents as system context.
    """

    def __init__(
        self,
        retriever: Callable[[str], List[RetrievalResult]],
        system_prefix: str = "Here are retrieved documents:",
        top_k: int = 5
    ):
        self.retriever = retriever
        self.system_prefix = system_prefix
        self.top_k = top_k

    def run(self, agent, state, user_message):
        query = state[-1]["content"]
        try:
            query_plan = QueryPlan.model_validate_json(query)
        except Exception as e:
            query_plan = QueryPlan(queries=[query], reasoning="", action="stop")

        docs: List[RetrievalResult] = []
        for q in query_plan.queries:
            docs.extend(self.retriever(q)[: self.top_k])
        docs.sort(key=lambda doc: doc.score, reverse=True)
        docs = list(set(docs[:self.top_k + 10]))[:self.top_k]

        state.append({
            "role": "system",
            "content": f"{self.system_prefix}\n" + "\n\n".join([doc.result for doc in docs])
        })

        return StepResult(messages=state, output=docs)

    async def async_run(self, agent, state, user_message):
        query = state[-1]["content"]

        try:
            query_plan = QueryPlan.model_validate_json(query)
        except Exception as e:
            query_plan = QueryPlan(queries=[query], reasoning="", action="stop")

        docs: List[RetrievalResult] = []
        # If retriever is async
        if asyncio.iscoroutinefunction(self.retriever):
            for q in query_plan.queries:
                rval = await self.retriever(q)  # type:ignore
                docs.extend(rval[: self.top_k])
            docs.sort(key=lambda doc: doc.score, reverse=True)
            docs = list(set(docs[:self.top_k + 10]))[:self.top_k]
        else:
            for q in query_plan.queries:
                docs.extend(self.retriever(q)[: self.top_k])
            docs.sort(key=lambda doc: doc.score, reverse=True)
            docs = list(set(docs[:self.top_k + 10]))[:self.top_k]

        state.append({
            "role": "system",
            "content": f"{self.system_prefix}\n" + "\n\n".join([doc.result for doc in docs])
        })

        return StepResult(messages=state, output=docs)
