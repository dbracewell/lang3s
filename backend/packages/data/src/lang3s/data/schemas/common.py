from typing import Annotated, Optional

from pydantic import BaseModel, Field, WithJsonSchema


class PaginatedQuery(BaseModel):
    cursor: Annotated[
        int | None,
        WithJsonSchema(
            {"nullable": True, "type": "integer", "minimum": 1, "default": 1}
        ),
    ] = 1
    limit: int = Field(default=25, ge=5)

    @property
    def offset(self) -> int:
        cursor = self.cursor or 1
        return (cursor - 1) * self.limit

    def generate_page(self, r: list) -> tuple[int | None, list]:
        cursor = self.cursor or 1
        if len(r) > self.limit:
            return cursor + 1, r[:-1]
        return None, r


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int = 0
    total_pages: int = 0
    next_cursor: int | None = None
    previous_cursor: int | None = None
