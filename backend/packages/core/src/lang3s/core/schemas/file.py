from typing import Any, Optional

from pydantic import BaseModel, Field


class File(BaseModel):
    path: Optional[str] = Field(default=None)
    docId: Optional[str] = Field(default=None)
    mime_type: str = Field(default="text/plain")
    encoding: Optional[str] = Field(default=None)
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
