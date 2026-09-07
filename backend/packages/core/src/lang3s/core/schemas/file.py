from typing import Any

from pydantic import BaseModel, Field


class File(BaseModel):
    path: str | None = Field(default=None)
    docId: str | None = Field(default=None)
    mime_type: str = Field(default="text/plain")
    encoding: str | None = Field(default=None)
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
