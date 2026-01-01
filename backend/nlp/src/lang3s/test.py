from typing import Annotated

from outlines.inputs import Chat
from pydantic import BaseModel

from lang3s.agent.llm import tool
from lang3s.app import Application
from lang3s.clients.topic_model_client import TopicModelClient
from lang3s.db import Database
from lang3s.maths import binarize
from lang3s.models import Embedder


@tool(name="get_weather", description="Gets the weather for a given location")
def get_weather(location: Annotated[str, "The location to retrieve weather for"]):
    return "76"


class Sentence(BaseModel):
    sentence: str


class Test(Application):
    def run(self):
        # client = TopicModelClient()
        # client.finalize()
        db = Database()
        db.refresh_views()
        print("Finished refreshing views")
        # Load model directly


#         from transformers import AutoTokenizer, AutoModelForCausalLM
#         import outlines
#
#         tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-4b-Instruct-2507")
#         model = outlines.from_transformers(
#             AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-4b-Instruct-2507").to("mps"),
#             tokenizer_or_processor=tokenizer)
#         #
#         # messages = [
#         #     {"role": "user", "content": "Give me an example sentence with Peter as the character."},
#         # ]
#         # inputs = tokenizer.apply_chat_template(
#         #     messages,
#         #     add_generation_prompt=True,
#         #     tools=[get_weather.tool.schema],
#         #     tokenize=True,
#         #     return_dict=True,
#         #     return_tensors="pt",
#         # ).to("mps")
#
#         chat = Chat()
#         chat.add_user_message("""
#         Given the following set of keywords and example sentences, generate a short (maximum 1 sentence)
#         name for the topic covered by the keywords and example sentences. The topic should be too generic or too
#         specific, but adequately describe the content. Please give the output as "name" or "netflix" like category.
#         Keywords: yukos, russian, rosneft, gazprom, russia
#         Example Sentences:
#         The Kremlin last year seized and sold Yukos' main production arm, Yugansk, to state-run oil group Rosneft for $9.3bn to offset a massive back tax bill.
# It has claimed that Russia imposed the huge tax bill and forced the sale of Yugansk as part of a campaign to destroy Yukos and its former owner Mihkail Khodorkovsky, who is facing a 10-year prison term in Russia for fraud and tax evasion.
# State-owned Rosneft bought the Yugansk unit for $9.3bn in a sale forced by Russia to part settle a $27.5bn tax claim against Yukos.
# Russian prosecutors are forcing the sale of the firm's most lucrative asset Yuganskneftegas to help pay a $27bn (£14bn) back tax bill, which they claim is owed by Yukos.
# By selling the Yukos unit to little-known Baikal and then to Rosneft, Russia is able to circumvent a host of tricky legal landmines, analysts said.
# Mr Khodorkovsky, who had funded liberal opposition groups, was arrested in October last year on fraud and tax evasion charges and is still in jail Analysts believe that if its production unit is auctioned off, it is likely to be bought up by a government-backed firm, like Gazprom, effectively bringing a large chunk of Russia's lucrative oil and gas industry back under state control.
# Yukos is currently suing four companies - Gazprom, its unit Gazpromneft, Rosneft and the shell company which won the bidding - for their part in Yugansk's disposal.
# The Russian government's argument for selling Yuganskneftegaz - the unit's full name - was that Yukos owed more than $27bn in back taxes for the years from 2000 onwards.
# The Russian government put Yukos's Yuganskneftegas subsidiary up for sale last week after hitting the company with a $27bn (£14bn) bill for back taxes and fines.
# The company is also seeking $20bn in a separate US lawsuit against Rosneft and Gazprom for their role in the sale of Yugansk.
# The Russian government forced the sale of Yukos' most lucrative asset as part of its action to enforce a $27bn back tax bill it says the company owes.
# Speaking on Tuesday, President Putin said Baikal was owned by individual investors who planned to build relationships with other Russian energy firms interested in the development of Yuganskneftegas.
# It had agreed to loan to an arm of Russian state gas firm Gazprom the money to bid for Yuganskneftegaz, as the Yukos unit is formally known.
# Speaking on NTV television, which is controlled by Gazprom, Mr Miller added that Yugansk, which was swallowed up by Rosneft late last year, will operate as a separate, state-owned oil firm headed by current Rosneft chief Sergei Bogdanchikov.
# Mystery surrounds new Yukos owner The fate of Russia's Yuganskneftegas - the oil firm sold to a little-known buyer on Sunday - is the subject of frantic speculation in Moscow.
# "Clearly the Chinese are trying to get some leverage [in Russia]," said Dmitry Lukashov, an analyst at brokerage Aton.
# The merger, backed by Russian authorities, will allow foreigners to trade in Gazprom shares.
# Rosneft, meanwhile, has agreed to merge with Gazprom, bringing a large chunk of Russia's very profitable oil business back under state control.
# Rosneft, meanwhile, has agreed to merge with Gazprom, bringing a large chunk of Russia's very profitable oil business back under state control.
# Russian newspapers have claimed that Baikal - which bought the Yuganskneftegas production unit for $9.4bn (261bn roubles, £4.8bn) on Sunday at a state provoked auction - has strong links with Surgutneftegas, Russia's fourth-biggest oil producer.
#         """)
#         outputs = model(chat,
#                         max_new_tokens=200)
#         print(outputs)
#         # print(get_weather.tool.arg_validator.model_validate_json(outputs))
#         # print(tokenizer.decode(outputs[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True))


if __name__ == "__main__":
    Test.from_cli().run_with_plugins()
