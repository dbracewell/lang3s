import asyncio
import os

from jsonlines import jsonlines
from lang3s.llm import LLMClient, Message
from lang3s.nlp.claim_extractor import ClaimList
from lang3s.parallel.core import Engine
from lang3s.parallel.manager import TaskManager

#     return f"""
# You are an expert linguist. Your task is to extract clear, standalone, and verifiable claims from a target SENTENCE, using the provided CONTEXT to fill in missing information. It IS possible to extract no claims.
#
# Type of Claim	Focus	Example regarding Smoking
# Fact	Truth/Existence	"Smoking increases the risk of lung cancer."
# Definition	Categorization	"Vaping should be defined as a form of smoking."
# Value	Morality/Worth	"It is wrong for companies to market cigarettes to teens."
# Policy	Action/Change	"The government should ban smoking in all public parks."
# Causation	Cause & Effect	"Second-hand smoke causes respiratory issues in non-smokers."
# Comparison	Analogy	"Regulating tobacco is like regulating alcohol; both are addictive substances."
# Contingency	Conditionality	"If smoking taxes increase, then smoking rates will decrease."
#
# Follow these strict rules for extraction:
# 1. Resolve Coreferences: Replace all pronouns (it, he, they, this, etc.) and vague references with the specific named entities they refer to from the CONTEXT.
# 2. Contextualize the Action: If the SENTENCE implies an action related to an event in the CONTEXT (e.g., an apology for X, or blaming Y for Z), explicitly include that event in your extracted claim so it makes complete sense on its own.
# 3. Make it Standalone: The extracted claim(s) must be completely understandable to a reader who has not seen the original text.
# 4. Split Compound Claims: If the SENTENCE makes multiple distinct factual assertions, separate them into a numbered list of individual claims.
# 5. Stay Grounded: Do not hallucinate or add outside knowledge. Only use facts present in the CONTEXT and SENTENCE.
# 6. Conciseness: Claims should be no more than 15 words.
# 7. Claims should be genetic statements: "Universial healthcare is good" NOT "The author believes Universial healthcare is good"
# 8. Claims must have the following:
#     1. A clear Source: Who is making the claim.
#     2. A clear Target: The target of the claim.
#     3. A type: Only Fact, Definition, Value, Policy, Causation, Comparison, or Contigency
# 9. Do not output the Source in the claim text only in the Source field.
#
# Follow these strict rules for extraction:
# 1. If you cannot resolve coreference and can only make a claim like "The man ...", "The woman...", or "The author..." DO NOT extract it is a claim.
#
#
# Here are examples of how to perform this task:
#
# Example 1:
# CONTEXT: Both are looking to Russia and China to provide future growth as western European markets are largely mature. Heineken's net income fell to 537m euros ($701m; £371m) during 2004, from 798m euro a year ago. It blamed weak demand in western Europe and currency losses.
# SENTENCE: It blamed weak demand in western Europe and currency losses.
# OUTPUT:
# - CLAIM: Weak demand in western Europe caused a decrease in Heineken's net income. SOURCE: Heineken TYPE: Causation SENTIMENT: negative
# - CLAIM: Currency losses caused a decrease in Heineken's net income. TYPE: Causation SENTIMENT: negative
#
# Example 2:
# CONTEXT: Marie Curie was a Polish and naturalized-French physicist and chemist. She was the first woman to win a Nobel Prize, the first person to win a Nobel Prize twice, and the only person to win a Nobel Prize in two scientific fields. Her husband, Pierre Curie, was a co-winner of her first Nobel Prize.
# SENTENCE: Her husband, Pierre Curie, was a co-winner of her first Nobel Prize.
# OUTPUT:
# - Pierre Curie was a co-winner of Marie Curie's first Nobel Prize. SOURCE: Author TYPE: Fact SENTIMENT: neutral
# - Pierre Curie was Marie Curie's husband. SOURCE: Author TYPE: Fact SENTIMENT: neutral
#
# Example 3:
# CONTEXT: My recent ex changed some settings on my phone to allow shared albums to come in, and a shared album I didn't even know existed from 2020 came in from that same ex who slammed into the tree. He said I was obsessed with all of my ex's and that there should be no photographic proof or trace of anything from the past if I am truly moved on. He went through my entire phone and texts from other people that were sent years ago-- like from 2016.
# SENTENCE: He went through my entire phone and texts from other people that were sent years ago-- like from 2016.
# OUTPUT:
# NO CLAIMS
#
# Output your result in valid JSON. Only output JSON in the provided schema and no other information.
#
# Now, extract the claim(s) for the following:
# {example}
# """
#


def create_prompt(example):
    return f"""
Role: You are a Linguistic Analyst specializing in Argumentative Structure. Your task is to deconstruct a given sentence into its fundamental logical components based on a specific formula.

Claim definition:
It is debatable: If everyone already agrees it is true (e.g., "The sun rises in the east"), it is a fact, not a claim. 
A claim must be something people can argue about.
It is assertive: It makes a clear stance rather than asking a question or being vague.

I start looking, and don't find any apps, browser history or anything of a gambling app.

The Formula:
Every claim consists of the following parts:
- Text: [REQUIRED]: The concise, self contained, and contextualized claim from which the following parts can be extracted or inferred.
- Target [REQUIRED]: The subject, entity, or concept the claim is about (the "who" or "what").
- Stance [REQUIRED]: The core assertion, position, or judgment being made about the target.
- Time [OPTIONAL]: The specific timeframe, period, or temporal limit of the claim.
- Cause/Condition [OPTIONAL]: The reason, trigger, or circumstance that necessitates or explains the stance (Only for Causation and Contingency claim types.).
- Type [REQUIRED]:
    - Fact:	Truth/Existence	"Smoking increases the risk of lung cancer."
    - Definition:Categorization	"Vaping should be defined as a form of smoking."
    - Value: Morality/Worth	"It is wrong for companies to market cigarettes to teens."
    - Policy: Action/Change	"The government should ban smoking in all public parks."
    - Causation: Cause & Effect	"Second-hand smoke causes respiratory issues in non-smokers."
    - Comparison: Analogy	"Regulating tobacco is like regulating alcohol; both are addictive substances."
    - Contingency: Conditionality	"If smoking taxes increase, then smoking rates will decrease."
- Type Confidence [REQUIRED]: low, medium, high confidence in the classification of the claim type. Give a realistic estimate on how well the text matches the type.
- Sentiment [REQUIRED]: positive/negative/neutral The sentinment of the Stance in regards to the Target.

Instructions:
Analyze the provided [TARGET SENTENCE].
If an optional component (Time or Cause) is not present in the sentence, label it as empty "".
Provide the output in a clean, structured list format.
If a TARGET SENTENCE does not contain a valid claim then output NO CLAIMS.
If a potential claim does not obviously fit into one of the types, then do not output it.

Claim Text:
Resolve Coreferences: Replace all pronouns (it, he, they, this, etc.) and vague references with the specific named entities they refer to from the CONTEXT.
Contextualize the Action: If the SENTENCE implies an action related to an event in the CONTEXT (e.g., an apology for X, or blaming Y for Z), explicitly include that event in your extracted claim so it makes complete sense on its own.
Make it Standalone: The extracted claim(s) must be completely understandable to a reader who has not seen the original text.
Split Compound Claims: If the SENTENCE makes multiple distinct factual assertions, separate them into a numbered list of individual claims.
Conciseness: Claims should be no more than 15 words. 
Stay Grounded: Do not hallucinate or add outside knowledge. Only use facts present in the CONTEXT and SENTENCE.

Important Restrictions:
If you cannot resolve coreference and can only make a claim like "The man ...", "The woman...", or "The author..." DO NOT extract it is a claim.


Here are examples of how to perform this task:

Example 1:
CONTEXT: Both are looking to Russia and China to provide future growth as western European markets are largely mature. Heineken's net income fell to 537m euros ($701m; £371m) during 2004, from 798m euro a year ago. It blamed weak demand in western Europe and currency losses.
SENTENCE: It blamed weak demand in western Europe and currency losses.
OUTPUT: 
- CLAIM: Weak demand in western Europe caused a decrease in Heineken's net income. 
  TARGET: Heineken's net income
  STANCE: decrease
  TYPE: Causation 
  CAUSE: Weak demand in western Europe
  SENTIMENT: negative
- CLAIM: Currency losses caused a decrease in Heineken's net income.
  TARGET: Heineken's net income
  STANCE: decrease
  TYPE: Causation 
  CAUSE: Currency losses
  SENTIMENT: negative
  
Example 2:
CONTEXT: Marie Curie was a Polish and naturalized-French physicist and chemist. She was the first woman to win a Nobel Prize, the first person to win a Nobel Prize twice, and the only person to win a Nobel Prize in two scientific fields. Her husband, Pierre Curie, was a co-winner of her first Nobel Prize.
SENTENCE: Her husband, Pierre Curie, was a co-winner of her first Nobel Prize.
OUTPUT: 
- CLAIM: Pierre Curie was a co-winner of Marie Curie's first Nobel Prize. 
  TARGET: Pierre Curie 
  STANCE: co-winner of Marie Curie's first Nobel Prize
  TYPE: Fact 
  SENTIMENT: neutral
- Pierre Curie was Marie Curie's husband.
  TARGET: Pierre Curie 
  STANCE: was Marie Curie's husband
  TYPE: Fact 
  SENTIMENT: neutral
  
Example 3:
CONTEXT: My recent ex changed some settings on my phone to allow shared albums to come in, and a shared album I didn't even know existed from 2020 came in from that same ex who slammed into the tree. He said I was obsessed with all of my ex's and that there should be no photographic proof or trace of anything from the past if I am truly moved on. He went through my entire phone and texts from other people that were sent years ago-- like from 2016.
SENTENCE: He went through my entire phone and texts from other people that were sent years ago-- like from 2016.
OUTPUT: 
NO CLAIMS 

Output your result in valid JSON. Only output JSON in the provided schema and no other information.

Now, extract the claim(s) for the following:
{example}
"""


client = LLMClient(model_name="gemma-4-26b-a4b-it")


async def perform_call(event):
    doc = event.data
    prompt = create_prompt(doc["text"])
    response = await client.chat_completion_last_event(
        messages=[Message.user(prompt)],
        response_model=ClaimList,
        temperature=0,
        stream=False,
    )
    if response.exception:
        print(response.exception)
    elif response.parsed:
        return doc["text"], response.parsed
    return None, None


async def main():
    with jsonlines.open(
        os.path.expanduser("~/prj/data/claims/claims_generation_dataset_v2.jsonl"), "w"
    ) as writer:
        with TaskManager(
            engine=Engine.ASYNC,
            workers=4,
        ) as tm:
            total_sentences = 0
            async for text, doc in tm.async_map(
                perform_call,
                jsonlines.open(
                    os.path.expanduser(
                        "~/prj/data/claims/claims_sentence_filtered_shuffled_dataset.jsonl"
                    )
                ),
            ):
                if text and doc:
                    total_sentences += 1
                    writer.write(
                        {
                            "messages": [
                                Message.user(
                                    f"Extract all claims from: {text}"
                                ).to_dict(),
                                Message.assistant(doc.model_dump_json()).to_dict(),
                            ]
                        }
                    )
                if total_sentences >= 20000:
                    break


if __name__ == "__main__":
    asyncio.run(main())
