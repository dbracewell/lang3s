from typing import Annotated

from lang3s.data.db import text_db
from lang3s.llm.tools import Desc, tool


@tool(description="Searches for information related to the given query.")
def document_search(query: Annotated[str, Desc("The query to search.")]):
    results = text_db.fts_sentence_search(query=query, limit=10)
    return results


@tool(description="Searches topics for information related to the given query.")
def topics_search(query: Annotated[str, Desc("The query to search.")]):
    results = text_db.fts_topic_search(query=query, limit=10)
    return results
