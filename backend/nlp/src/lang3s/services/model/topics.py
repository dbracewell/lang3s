from typing import Any, NamedTuple, Optional

from pydantic import BaseModel


class TopicData(BaseModel):
    id: str
    name: str
    support: int


class Task(NamedTuple):
    method: str
    id: str
    data: Any

    def __hash__(self):
        return hash(self.id)


class TopicUpdateRequest(BaseModel):
    name: Optional[str]
    is_fixed: Optional[bool]
