from typing import List, Optional, Type
from pydantic import BaseModel
from lang3s.agent.shared_types import StepResult, AgentStep
from lang3s.agent.persona import Persona, PersonaMode, PersonaAwareStep


class RewriteStep(PersonaAwareStep):
    persona_modes = [PersonaMode.TONE, PersonaMode.ANALYSIS, PersonaMode.SUMMARIZATION]

    def __init__(self,
                 mode: PersonaMode = PersonaMode.PERSPECTIVE,
                 replace_user_message: bool = False,
                 history: int = 1,
                 instructions: Optional[str] = None):
        super().__init__(mode)
        self.replace_user_message = replace_user_message
        self.instructions = instructions
        self.history = history if history > 0 else 1

    def run_no_persona(self, agent, state: List[dict], user_message: str) -> StepResult:
        if self.instructions is None:
            return StepResult(messages=state, output=user_message)
        last_state = state[-1]["content"]
        prompt = f"""
        {self.instructions}
        
        Include the last {self.history} messages as context.
        
        {last_state}
        """
        return self.__run_prompt(agent, state, prompt)

    def __run_prompt(self, agent, state, prompt: str, is_persona: bool = False) -> StepResult:
        prompt += "\nOutput your result in plain text. Only output the rewritten text. Do not refer to the user. "
        state.append({"role": "user", "content": prompt})
        result = agent.orchestrator.chat(state)
        rewritten = result["content"]

        if self.replace_user_message:
            state.append({"role": "user", "content": rewritten})
        else:
            state.append({
                "role": "system",
                "content": f"{'Persona-style ' if is_persona else ''}paraphrase of user message: {rewritten}",
            })

        return StepResult(messages=state, output=rewritten)

    def run_with_persona(
        self,
        agent,
        state: List[dict],
        user_message: str,
        persona: Persona,
        mode: PersonaMode,
    ) -> StepResult:
        task = ""
        if mode == PersonaMode.PERSPECTIVE or mode == PersonaMode.TONE:
            task = (
                "Rewrite the user's message in the persona's voice while preserving the exact meaning. "
                "Do not add or remove information."
            )
        prompt = self.build_persona_prompt(persona, mode, task, user_message, history=self.history)
        return self.__run_prompt(agent, state, prompt, is_persona=True)


class StructuredOutputStep(AgentStep):
    def __init__(
        self,
        response_model: Type[BaseModel],
        instructions: Optional[str] = None,
        max_retries: int = 3,
    ):
        self.response_model = response_model
        self.instructions = instructions or ""
        self.max_retries = max_retries

    def run(self, agent, state, user_message):
        # Add wrap-up instruction
        if self.instructions:
            state.append({"role": "user", "content": self.instructions})

        for attempt in range(self.max_retries):
            result = agent.orchestrator.chat(
                state,
                response_model=self.response_model,
                tool_names=None,
            )

            content = result["content"]

            try:
                parsed = self.response_model.model_validate_json(content)
            except Exception as e:
                # Ask model to fix itself
                state.append({
                    "role": "user",
                    "content": f"Your output didn't match the schema. Error: {e}. Try again."
                })
                continue

            # good result
            state.append({"role": "assistant", "content": content})
            return StepResult(messages=state, output=parsed)

        raise RuntimeError("StructuredOutputStep failed after retries")

    async def async_run(self, agent, state, user_message):
        if self.instructions:
            state.append({"role": "user", "content": self.instructions})

        for attempt in range(self.max_retries):
            result = await agent.orchestrator.achat(
                state,
                response_model=self.response_model,
                tool_names=None,
            )

            content = result["content"]

            try:
                parsed = self.response_model.model_validate_json(content)
            except Exception as e:
                state.append({
                    "role": "user",
                    "content": f"Your output didn't match the schema. Error: {e}. Try again."
                })
                continue

            state.append({"role": "assistant", "content": content})
            return StepResult(messages=state, output=parsed)

        raise RuntimeError("StructuredOutputStep failed after retries")
