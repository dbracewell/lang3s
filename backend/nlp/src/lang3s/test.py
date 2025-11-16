import logging
from typing import List, cast
from typing import Literal

import jsonlines
from pydantic import BaseModel, Field
from tqdm import tqdm

from lang3s.agent.agent import Agent, ToolExecutionStep, ToolStep, \
    PersonaUserRewriteStep
from lang3s.models.llm import global_tool_registry, orchestrator


# files = []
# with jsonlines.open("/Users/ik/Library/Mobile Documents/com~apple~CloudDocs/project_reddit/llm_annotated.jsonl",
#                     mode="r") as reader:
#     for item in reader:
#         files.append(File(content=item["sentence"],
#                           metadata={
#                               "correct": str(item["correct"]),
#                               "distortion": item["category"],
#                           }
#                           ))
#
# docs = pipeline(files, write_to_db=False)
# correct = defaultdict(int)
# incorrect = defaultdict(int)
# total = defaultdict(int)
# output = []
# for doc in docs:
#     gold = doc.metadata["distortion"] if doc.metadata["correct"] == "True" else "None"
#     pred = doc.text.sentences[0].metadata.get("distortion", "None")
#     if doc.text.sentences[0]["toxic"] == "1":
#         print(doc.text.sentences[0])
#     total[gold] += 1
#     if gold == pred:
#         correct[pred] += 1
#     else:
#         incorrect[pred] += 1
#         record = {"gold": gold, "pred": pred, "sentence": doc.text.sentences[0].text}
#         output.append(record)
#
# all_cats = set(correct.keys()).union(set(incorrect.keys()))
# for category in sorted(all_cats):
#     c = correct.get(category, 0)
#     i = incorrect.get(category, 0)
#     t = total[category]
#     p = c / (c + i)
#     r = c / t
#     f = (2 * p * r) / (p + r)
#     print(category, f"{p:.2f}", f"{r:.2f}", f"{f:.2f}")
#
# with jsonlines.open("../../output.jsonl", mode="w") as writer:
#     writer.write_all(output)
#
# exit(0)


class Annotation(BaseModel):
    category: Literal[
        "All-or-Nothing Thinking",
        "Catastrophizing",
        "Personalization",
        "Mind Reading & Fortune Telling",
        "Labeling & Self-Judgment",
        "Emotional Reasoning & Hopelessness",
        "Discounting Positives & Imposter Syndrome",
        "Should & Must Statements"] = Field(
        description="The category of the annotation")
    sentence: str = Field(description="The sentence of the annotation")

    def __eq__(self, other):
        return self.sentence == other.sentence

    def __hash__(self):
        return hash(self.sentence)


class Annotations(BaseModel):
    annotations: List[Annotation]


# completion = cast(List[Annotations], generate_text(
#     [
#         Message(role="system",
#                 content="You are helpful data generator."),
#         Message(role="user",
#                 content=f"""Please generate 20 random example sentences for the cognitive distortions that could be see on Reddit, Twitter, or Facebook with one of the following labels:
#                                         'All-or-Nothing Thinking',
#                                         'Catastrophizing',
#                                         'Personalization',
#                                         'Mind Reading & Fortune Telling',
#                                         'Labeling & Self-Judgment',
#                                         'Emotional Reasoning & Hopelessness',
#                                         'Discounting Positives & Imposter Syndrome',
#                                         'Should & Must Statements'.
#                             """),
#     ],
#     # tools=[search.tool]
#     schema=Annotations,
# ))

PERSONAS = {
    "gen_z": {
        "name": "Gen Z Speaker",
        "description": (
            "Casual, internet-savvy tone. Uses memes, slang, emojis, softeners like "
            "'lowkey', 'fr', 'no cap', 'bet', 'vibes'. Friendly, upbeat, informal."
        )
    },
    "aave": {
        "name": "African American Vernacular English (AAVE)",
        "description": (
            "Rhythmic, conversational, culturally grounded speech patterns. Uses AAVE syntax, "
            "lexical choices, and idioms authentically but respectfully, without exaggeration."
        )
    },
    "blue_collar": {
        "name": "Blue Collar Worker",
        "description": (
            "Straightforward, plainspoken, practical. Uses hands-on metaphors, simple language, "
            "down-to-earth tone. Avoids fancy jargon."
        )
    },
    "formal_corporate": {
        "name": "Formal Corporate Executive",
        "description": (
            "Professional, structured, polished. Prefers clarity, conciseness, and strategic framing. "
            "Avoids slang; uses business terminology."
        )
    },
    "anime_character": {
        "name": "Anime Protagonist",
        "description": (
            "Energetic, expressive, dramatic tone with emotional highs. Uses Japanese-flavored English, "
            "onomatopoeia, and exaggerated enthusiasm."
        )
    },
    "republican": {
        "name": "Republican Political Perspective",
        "description": (
            "A worldview emphasizing limited federal government, free-market "
            "economics, strong national defense, traditional values, and skepticism "
            "toward high taxation and large bureaucratic programs. Tone is direct, "
            "principled, focused on constitutional grounding and personal responsibility. "
            "Avoid stereotypes or exaggerated rhetoric."
        )
    }
}


class SearchArgs(BaseModel):
    query: str


class SearchResult(BaseModel):
    results: list[str]


KB = [
    "Brazil is the largest country in South America.",
    "Brazil's capital is Brasília.",
    "Brazil is known for the Amazon rainforest.",
]


def simple_retriever(q: str):
    q = q.lower()
    return [doc for doc in KB if q in doc.lower()]


class FinalAnswer(BaseModel):
    answer: str
    reasoning: str
    sources: list[str]


@global_tool_registry.tool(
    args_model=SearchArgs,
    result_model=SearchResult,
    description="Searches the in-memory KB for information."
)
def search(query: str) -> SearchResult:
    matches = simple_retriever(query)
    return SearchResult(results=matches)


agent = Agent(orchestrator=orchestrator)
agent.add_step(PersonaUserRewriteStep(
    persona_name="Republican Political Perspective",
    persona_description=PERSONAS["republican"]["description"],
    replace_user_message=False
))
agent.add_step(ContentAnalysisStep())  # extracts topics/claims
agent.add_step(ResearchPlanningStep())  # builds search queries
agent.add_step(ToolStep(
))
agent.add_step(ToolExecutionStep())
agent.add_step(SynthesisStep())  # neutral factual synthesis
agent.add_step(PerspectiveRewriteStep(
    persona_name="Republican Political Perspective",
    persona_description=PERSONAS["republican"]["description"],
))

user_query = "brazil"
final = agent.run(user_query)
print(final)

# cm = generate_text(
#     [
#         Message(role="system",
#                 content="You are helpful data retriever. Use the provided tools to search for the required data. Do not generate results, instead use the provided search tool."),
#         Message(role="user",
#                 content="""
#                 Please search the database using the search tool to find data related to Brazil.
#                 """),
#     ],
#     tools=[search.tool],
#     schema=SearchResults,
#     # force_tool_call=True,
# )
# print(cm[0])
# j = cm[0].replace("```json\n", "").replace("```\n", "")
# doc = json.loads(j)
# print(doc)

exit()
with jsonlines.open("../../test.jsonl", mode="w") as writer:
    for _ in tqdm(range(50)):
        annotations = []
        try:
            completion = cast(List[Annotations], generate_text(
                [
                    Message(role="system",
                            content="You are helpful data generator."),
                    Message(role="user",
                            content=f"""Please generate 20 random example sentences for the cognitive distortions that could be see on Reddit, Twitter, or Facebook with one of the following labels:         
                                        'All-or-Nothing Thinking',
                                        'Catastrophizing',
                                        'Personalization',
                                        'Mind Reading & Fortune Telling',
                                        'Labeling & Self-Judgment',
                                        'Emotional Reasoning & Hopelessness',
                                        'Discounting Positives & Imposter Syndrome',
                                        'Should & Must Statements'.
                            """),
                ],
                # tools=[search.tool]
                schema=Annotations,
            ))
        except Exception as e:
            logging.error(e)
            continue

        for item in completion:
            for sentence in item.annotations:
                try:
                    cm = cast(List[Annotations], generate_text(
                        [
                            Message(role="system",
                                    content="You are helpful data annotator."),
                            Message(role="user",
                                    content=f"Please search the database using the search function to find examples of the {sentence.category} which using the following sentence `{sentence.sentence}` to query data."),
                        ],
                        tools=[search.tool],
                        schema=Annotations,
                        force_tool_call=True,
                    ))
                except Exception as e:
                    logging.error(e)
                    continue

                for result in cm:
                    for finala in result.annotations:
                        annotations.append(finala)

        for annotation in set(annotations):
            writer.write(annotation.model_dump())
