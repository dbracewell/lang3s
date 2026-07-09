from __future__ import annotations

from typing import TYPE_CHECKING, Counter

from pydantic import BaseModel, Field
from spacy.tokens import Doc

from lang3s.agent.events import AgentEvent, AgentEventType
from lang3s.core.decorators import async_retry
from lang3s.llm import ToolCall
from lang3s.nlp.core import CoreLanguageProcessor
from lang3s.nlp.pipeline.langdetect import detect_language

from .strategy import Strategy, StrategyResult

if TYPE_CHECKING:
    from ..session import Session


class QueryFormat(BaseModel):
    queries: list[str] = Field(description="A list of search queries.")


class DiscoveryStrategy(Strategy[BaseModel]):
    def __init__(
        self,
        search_tool: str,
        allow_random_search: bool = True,
        rounds: int = 5,
        queries_per_round: int = 5,
        **kwargs,
    ):
        super().__init__()
        self.search_tool = search_tool
        self.rounds = rounds
        self.queries_per_round = queries_per_round
        self.allow_random_search = allow_random_search
        self._kwargs = kwargs

    async def run(self, session: Session) -> StrategyResult[BaseModel]:
        if not session.available_tools:
            return StrategyResult.from_exception(Exception("No available tools found."))

        tool_definitions = None
        for func in session.available_tools:
            if func.tool.name == self.search_tool:  # type:ignore
                tool_definitions = func.tool  # type: ignore
                break

        if tool_definitions is None:
            return StrategyResult.from_exception(
                Exception(f"Tool {self.search_tool} not found.")
            )

        discovered_terms = Counter()
        tool_id = 0
        try:
            session.state.max_progress += self.rounds * 3 + 1

            for round_idx in range(self.rounds):
                terms = [k[0] for k in discovered_terms.most_common(150) if k[1] > 1]
                random_search = ""
                if self.allow_random_search and round_idx == 0:
                    random_search = (
                        "If no clues exist, you MUST generate '*' as one of "
                        "your new search queries to retrieve random sentences "
                        "for the corpus. "
                    )
                probe_prompt = ""
                if session.state.task:
                    probe_prompt = f"User Task:\n{session.state.task.strip()}\n"

                probe_prompt += (
                    f"You are exploring an unknown corpus.\n"
                    f"You must explore the corpus using only the search tool. "
                    f"No prior knowledge is available. Begin generating probe queries."
                    f"Based on all previous discoveries, generate "
                    f"{self.queries_per_round} "
                    f"new search queries that are **diverse** and **exploratory**.\n"
                    f"If no clues exist, start with extremely broad probes such as: "
                    f"'a', 'the', 'data', 'report', 'sports', 'economy', 'business', "
                    "'computers', 'life', 'entertainment', etc. "
                    f"{random_search}"
                    f"Be sure to ONLY GENERATE {self.queries_per_round} new "
                    "search queries.\n"
                    f"\n\nDiscovered so far: {sorted(terms)}"
                )
                session.state.add_user_message(probe_prompt)

                @async_retry(
                    max_retries=3,
                    on_exceed_attempts=lambda ex: AgentEvent(
                        exception=ex, type=AgentEventType.ERROR
                    ),
                )
                async def generate_queries():
                    self._response_model = QueryFormat
                    r = await self._chat_to_completion(session)
                    self._response_model = None
                    if r.exception:
                        raise result.exception
                    return r

                result = await generate_queries()
                if result.exception:
                    return StrategyResult.from_exception(result.exception)

                query_result: QueryFormat = result.parsed  # type: ignore
                tool_calls: list[ToolCall] = []
                for query in list(set(query_result.queries))[: self.queries_per_round]:
                    discovered_terms[query] += 1
                    tool_calls.append(
                        ToolCall(
                            is_async=tool_definitions.is_async,
                            arguments={"query": query},
                            name=tool_definitions.name,
                            arguments_type=tool_definitions.arg_validator,
                            tool_call_id=str(tool_id),
                            function=tool_definitions.function,
                        )
                    )
                    session.forward_event(
                        AgentEvent.tool_call_complete_event(tool_calls[-1])
                    )
                    tool_id += 1

                await self._async_run_tools(session, tool_calls)
                await session.compact()
                result = await self._chat_to_completion(session)
                if result.exception:
                    return StrategyResult.from_exception(result.exception)

                summary_prompt = (
                    "Based on the new results, summarize what we "
                    "learned about the corpus.\n"
                    "Identify new topics, entity types, recurring "
                    "formats, or other patterns.\n\n"
                    "Be specific and list clearly observable characteristics."
                )
                session.state.add_user_message(summary_prompt)
                result = await self._chat_to_completion(session, **self._kwargs)
                if result.exception:
                    return StrategyResult.from_exception(result.exception)

                discovered_terms.update(self.extract_terms(result.content or ""))
                session.state.progress += 1
                await session.compact()

            final_prompt = (
                "Using all exploration rounds, produce a final characterization of "
                "the corpus in markdown format.\n"
                "Include:\n"
                "- Main topics\n"
                "- Subtopics\n"
                "- Notable entities\n"
                "- File/document types\n"
                "- Styles or patterns\n"
                "- Any ontology or taxonomy that emerges\n"
                "- Known gaps or unknowns\n"
            )
            session.state.add_user_message(final_prompt)
            result = await self._chat_to_completion(session, **self._kwargs)
            if result.exception:
                return StrategyResult.from_exception(result.exception)

            return StrategyResult.from_agent_event(result)
        except Exception as e:
            return StrategyResult.from_exception(e)

    def extract_terms(self, doc: str):
        language = detect_language(doc)
        processor = CoreLanguageProcessor()
        sdoc: Doc = processor.get_pipeline(language)(doc)
        keywords = []
        import re

        try:
            for chunk in sdoc.noun_chunks:
                t = ""
                for token in chunk:
                    if not token.is_stop:
                        t += token.lemma_ + " "
                t = t.strip()
                if len(t) > 3 and re.match(r"^[A-Za-z ]+$", t):
                    keywords.append(t.lower())
        except Exception:
            for token in sdoc:
                if not token.is_stop:
                    t = token.lemma_.lower()
                    if len(t) > 3 and re.match(r"^[A-Za-z]+$", t):
                        keywords.append(t)
        return keywords
