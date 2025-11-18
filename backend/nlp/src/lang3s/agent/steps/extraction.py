import json
import textwrap

from lang3s.agent.helpers import clean_thinking
from lang3s.agent.shared_types import AgentState, AgentStep, StepResult


class CategorizationStep(AgentStep):

    def __init__(self, name: str = "CategorizationStep"):
        AgentStep.__init__(self, name)

    def _execute(self, agent, state: AgentState) -> StepResult:
        plan = state.last_plan
        if plan is None:
            return StepResult(success=False)

        category = plan.target_category
        last_output = clean_thinking(state.last_output)

        if last_output is None:
            state.update({"role": "user",
                          "content": textwrap.dedent(f"""
                                   {state.create_base_prompt()}
                                   
                                   No data was given to categorize. 
                                   Please either generate examples or retrieve data to be categorized.
                                   """),
                          "status": "failed"})
            resp = agent.orchestrator.chat(state.get_llm_messages())
            return StepResult(output=resp["content"])

        prompt = textwrap.dedent(f"""
                        {state.create_base_prompt()}
                        
                        Categorize each sentence into:
                        - "{category}"
                        - "None" (if unrelated)
                        
                        Sentences:
                        {json.dumps(last_output, indent=2)}
                        
                        Output format:
                        [
                          {{"sentence": "...", "category": "..."}},
                          ...
                        ]
                    """)

        state.update({"role": "user", "content": prompt})
        resp = agent.orchestrator.chat(state.get_llm_messages())

        try:
            categories = json.loads(resp["content"])
        except:
            categories = []

        state.update({"role": "assistant", "content": resp["content"]})
        return StepResult(output=categories)
