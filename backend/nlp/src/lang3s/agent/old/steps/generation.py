from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING, Optional, Type

if TYPE_CHECKING:
    from lang3s.agent import Agent

from pydantic.main import BaseModel

from lang3s.agent.old.shared_types import (
    AgentState,
    AgentStep,
    ExampleList,
    PersonaAwareStep,
    PersonaMode,
    StepResult,
)


class GenerationStep(PersonaAwareStep):
    def __init__(
        self,
        prompt: Optional[str] = None,
        response_model: Optional[Type[BaseModel]] = None,
        max_retries: int = 3,
        name: str = "GenerationStep",
        mode: PersonaMode = PersonaMode.PERSPECTIVE,
    ):
        super().__init__(mode=mode, name=name)
        self.prompt = prompt or "Generate text based on the following content"
        self.response_model = response_model
        self.max_retries = max_retries

    async def _run_prompt(self, agent: "Agent", state: AgentState) -> StepResult:
        for _ in range(self.max_retries):
            result = await agent.orchestrator.achat(
                state.get_llm_messages(), response_model=self.response_model
            )
            content = result["content"]
            if self.response_model is not None:
                try:
                    parsed = self.response_model.model_validate_json(content)
                except Exception as e:
                    state.update(
                        {
                            "role": "user",
                            "content": f""""
                            {state.create_base_prompt(self.mode)}
                            
                            ERROR:
                            Your output didn't match the schema. Error: {e}. Try again.
                        """,
                        }
                    )
                    continue
                state.update({"role": "assistant", "content": content})
                return StepResult(output=parsed)

            state.update({"role": "assistant", "content": content})
            return StepResult(output=content)

        raise RuntimeError("GenerationStep failed after retries")

    async def _execute(
        self,
        agent,
        state: AgentState,
    ) -> StepResult:
        prompt = textwrap.dedent(f"""
                    {state.create_base_prompt(self.mode)}
                                               
                    {self.prompt if self.prompt else ""}
                    """)

        if self.response_model is None:
            prompt += "\nYou MUST output in plain text. Only output the text. Do not refer to the user or provide any other information."
        else:
            prompt += f"\nOutput your result in json matching the following schema\n{self.response_model.model_json_schema()}\n\n"

        state.update({"role": "user", "content": prompt.strip()})
        return await self._run_prompt(agent, state)


class SummarizationStep(GenerationStep):
    def __init__(self, name: str = "SummarizationStep"):
        prompt = "Summarize the given content keeping the summary concise, accurate, and grounded with a neutral tone, without adding stylistic or worldview modifications."
        GenerationStep.__init__(
            self, mode=PersonaMode.SUMMARIZATION, prompt=prompt, name=name
        )


class AnalysisStep(GenerationStep):
    def __init__(self, name: str = "AnalysisStep"):
        prompt = "Analyze the content highlighting the key topics, claims, and entities while operating with a neutral tone, without adding stylistic or worldview modifications."
        GenerationStep.__init__(
            self, mode=PersonaMode.ANALYSIS, prompt=prompt, name=name
        )


class PerspectiveStep(GenerationStep):
    def __init__(self, name: str = "PerspectiveStep"):
        prompt = "Give your perspective or reflection on the content operating with a neutral tone, without adding stylistic or worldview modifications."
        GenerationStep.__init__(
            self, mode=PersonaMode.PERSPECTIVE, prompt=prompt, name=name
        )


class ExampleGenerationStep(AgentStep):
    def __init__(self, name: str = "ExampleGeneration"):
        AgentStep.__init__(self, name=name)

    async def _execute(self, agent, state: AgentState) -> StepResult:
        plan = state.last_plan

        if plan is None:
            return StepResult(success=False, output=None)

        prompt = textwrap.dedent(f"""
                {state.create_base_prompt()}
                
                Generate 20 examples of the given target category.
                
                Target Category:
                "{plan.target_category}"
                
                Rules:
                - Each example must be one standalone sentence.
                - Make examples as diverse as possible.
                - They should NOT be real sentences from the corpus.
                - Do not include offensive or unsafe content.
                - Output in the following format:
                   {ExampleList.model_json_schema()}
                """)

        state.update({"role": "user", "content": prompt})
        resp = await agent.orchestrator.achat(
            state.get_llm_messages(), response_model=ExampleList
        )
        content = resp["content"]

        try:
            parsed = ExampleList.model_validate_json(content).examples
            state.cache["examples"] = state.cache.get("examples", 0) + len(parsed)
            state.update(
                {
                    "role": "system",
                    "content": f"Currently, {state.cache['examples']} examples of {plan.target_category} have been generated.",
                }
            )
        except Exception:
            parsed = content

        state.update({"role": "assistant", "content": resp["content"]})
        return StepResult(output=parsed)
