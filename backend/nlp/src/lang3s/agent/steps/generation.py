from typing import List, Optional
import json
from lang3s.agent.shared_types import AgentStep, StepResult
from lang3s.agent.persona import PersonaAwareStep, PersonaMode, Persona


class GenerationStep(PersonaAwareStep):
    def __init__(self,
                 prompt: Optional[str] = None,
                 history: int = 0,
                 mode: PersonaMode = PersonaMode.PERSPECTIVE):
        super().__init__(mode)
        self.prompt = prompt or "Generate text based on the following content"
        self.history = history

    def run_no_persona(self, agent, state: List[dict], user_message: str) -> StepResult:
        prompt = self.prompt
        if self.history > 0:
            prompt += f"\nInclude the last {self.history} messages as context.\n\n"
        state.append({"role": "user", "content": self.prompt})

        result = agent.orchestrator.chat(state)
        content = result["content"]

        state.append({"role": "assistant", "content": content})
        return StepResult(messages=state, output=content)

    def run_with_persona(
        self,
        agent,
        state: List[dict],
        user_message: str,
        persona: Persona,
        mode: PersonaMode,
    ) -> StepResult:
        if self.prompt is None:
            state.append({"role": "user", "content": self.prompt})
        prompt = self.build_persona_prompt(persona,
                                           task_instructions="Generate text based on the following content",
                                           content=user_message,
                                           history=self.history,
                                           mode=mode)
        prompt += "\nOutput your result in plain text. Only output the rewritten text. Do not refer to the user. "
        state.append({"role": "user", "content": prompt})
        result = agent.orchestrator.chat(state)
        content = result["content"]

        state.append({"role": "assistant", "content": content})
        return StepResult(messages=state, output=content)


class SummarizationStep(GenerationStep):

    def __init__(self, history=0):
        prompt = "Summarize the given content keeping the summary concise, accurate, and grounded with a neutral tone, without adding stylistic or worldview modifications."
        GenerationStep.__init__(self, mode=PersonaMode.SUMMARIZATION, history=history, prompt=prompt)


class AnalysisStep(GenerationStep):

    def __init__(self, history=0):
        prompt = "Analyze the content highlighting the key topics, claims, and entities while operating with a neutral tone, without adding stylistic or worldview modifications."
        GenerationStep.__init__(self, mode=PersonaMode.ANALYSIS, history=history, prompt=prompt)


class PerspectiveStep(GenerationStep):

    def __init__(self, history=0):
        prompt = "Give your perspective or reflection on the content operating with a neutral tone, without adding stylistic or worldview modifications."
        GenerationStep.__init__(self, mode=PersonaMode.PERSPECTIVE, history=history, prompt=prompt)


class ExampleGenerationStep(AgentStep):

    def run(self, agent, state: List[dict], user_message: str) -> StepResult:
        plan = agent.state_cache["last_plan"]

        prompt = f"""
Generate 10 example sentences for the category:
"{plan.target_category}"

Rules:
- Each example must be one standalone sentence.
- Make examples as diverse as possible.
- They should NOT be real sentences from the corpus.
- Do not include offensive or unsafe content.
- Output as a JSON list of strings.
"""
        state.append({"role": "user", "content": prompt})
        resp = agent.orchestrator.chat(state)

        try:
            examples = json.loads(resp["content"])
        except:
            examples = []

        state.append({"role": "assistant", "content": resp["content"]})

        return StepResult(messages=state, output=examples)
