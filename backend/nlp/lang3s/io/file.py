from typing import Dict, Optional

from pydantic import BaseModel, Field


class File(BaseModel):
    path: str
    mime_type: str
    encoding: Optional[str] = Field(default=None)
    content: str
    metadata: Dict[str, str] = Field(default_factory=dict)
