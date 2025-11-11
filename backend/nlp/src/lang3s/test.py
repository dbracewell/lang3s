from typing import List

from pydantic import BaseModel, Field

from lang3s.db import TextDatabase
from lang3s.models import Embedder
from lang3s.models.llm import Message, tool
from lang3s.models.llm import generate_text


class ProductInfo(BaseModel):
    name: str = Field(description="The name of the product")
    category: str = Field(description="The category the product belongs to")
    price: float = Field(description="The price of the product")
    features: list[str] = Field(description="A list of key features of the product")


embedder = Embedder()
text_db = TextDatabase()


def validate_positive_int(func):
    def wrapper(*args, **kwargs):
        for arg in args:
            if isinstance(arg, int) and arg <= 0:
                raise ValueError("All integer arguments must be positive.")
        return func(*args, **kwargs)

    return wrapper


@tool(
    description="Queries the text database and retrieves results for the given question",
    params={
        "question": "The question to ask the dataset"
    }
)
def query(question: str) -> List[str]:
    results = text_db.sentence_search(embedder([question]).sentence_embeddings[0],
                                      embedder.dimensions / 2, limit=10)
    return results


completion = generate_text(
    [
        Message(role="system",
                content="You are helpful information extractor. "
                        "Please use the query function to find information about the question."),
        Message(role="user",
                content="Please tell me about Malcolm Glazer. Please do not provide information other than what directly answers the question."),
    ],
    tools=[query.tool],
)
for item in completion:
    print(item)
