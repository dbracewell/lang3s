from typing import List, Optional

from pydantic import BaseModel, RootModel

from lang3s.services.models.common import PaginatedResponse


class DocumentInfo(BaseModel):
    id: str
    title: str
    snippet: str


class DocumentListResponse(PaginatedResponse[DocumentInfo]):
    pass
