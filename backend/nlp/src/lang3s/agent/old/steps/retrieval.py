import asyncio
from typing import Callable, List

from lang3s.agent.old.shared_types import (
    AgentState,
    AgentStep,
    QueryPlan,
    RetrievalResult,
    StepResult,
)


class RetrievalStep(AgentStep):
    """
    Calls a retriever and injects retrieved documents as system context.
    """

    def __init__(
        self,
        retriever: Callable[[str], List[RetrievalResult]],
        system_prefix: str = "Here are retrieved documents:",
        top_k: int = 5,
        name: str = "RetrievalStep",
    ):
        AgentStep.__init__(self, name)
        self.retriever = retriever
        self.system_prefix = system_prefix
        self.top_k = top_k

    async def _execute(
        self,
        agent,
        state: AgentState,
    ):
        query_plan = state.last_output

        if query_plan is None or not isinstance(query_plan, QueryPlan):
            query_plan = QueryPlan(
                queries=[state.messages[-1]["content"]], reasoning="", action="stop"
            )

        docs: List[RetrievalResult] = []
        for q in query_plan.queries:
            if asyncio.iscoroutinefunction(self.retriever):
                rval = await self.retriever(q)  # type: ignore
            else:
                rval = self.retriever(q)
            docs.extend(rval[: self.top_k])

        docs.sort(key=lambda doc: doc.score, reverse=True)
        docs = list(set(docs[: self.top_k + 10]))[: self.top_k]

        state.update(
            {
                "role": "system",
                "content": f"{self.system_prefix}\n"
                + "\n\n".join([doc.result for doc in docs]),
            }
        )

        return StepResult(output=docs)
