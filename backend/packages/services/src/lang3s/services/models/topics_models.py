from typing import Any, NamedTuple, Optional

from pydantic import BaseModel


class TopicData(BaseModel):
    id: str
    name: str
    support: int


class Task(BaseModel):
    method: str
    id: str
    data: Any


class TopicUpdateRequest(BaseModel):
    name: Optional[str]
    is_fixed: Optional[bool]
