import json
from typing import List

from lang3s.agent.shared_types import AgentStep, StepResult


class CategorizationStep(AgentStep):

    def run(self, agent, state: List[dict], user_message: str) -> StepResult:
        plan = agent.state_cache["last_plan"]
        category = plan.target_category

        if "last_output" not in state:
            state.append({"role": "user",
                          "content": "No data was given to categorize. Please either generate examples or retrieve data to be categorized."})
            resp = agent.orchestrator.chat(state)
            return StepResult(messages=state, output=resp["content"], terminated=False)

        retrieved = agent.state_cache["last_output"]
        prompt = f"""
Categorize each sentence into:
- "{category}"
- "None" (if unrelated)

Sentences:
{json.dumps(retrieved, indent=2)}

Output format:
[
  {{"sentence": "...", "category": "..."}},
  ...
]
"""
        state.append({"role": "user", "content": prompt})
        resp = agent.orchestrator.chat(state)

        try:
            categories = json.loads(resp["content"])
        except:
            categories = []

        state.append({"role": "assistant", "content": resp["content"]})
        return StepResult(messages=state, output=categories, terminated=False)
