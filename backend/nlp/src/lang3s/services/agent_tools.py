from typing import Annotated

from lang3s.agent.llm import Desc, tool
from lang3s.db import TextDatabase


@tool(description="Searches for information related to the given query.")
def document_search(query: Annotated[str, Desc("The query to search.")]):
    text_db = TextDatabase()
    results = text_db.search(query=query, limit=10)
    return results


@tool(description="Searches topics for information related to the given query.")
def topics_search(query: Annotated[str, Desc("The query to search.")]):
    text_db = TextDatabase()
    results = text_db.search_topics(query=query, limit=10)
    return results
