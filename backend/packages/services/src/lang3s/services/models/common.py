from typing import Optional

from pydantic import BaseModel, Field


class PaginatedQuery(BaseModel):
    cursor: int = Field(default=1, ge=1)
    limit: int = Field(default=5, ge=5)

    @property
    def offset(self) -> int:
        return (self.cursor - 1) * self.limit

    def generate_page(self, r: list) -> tuple[int | None, list]:
        if len(r) > self.limit:
            return self.cursor + 1, r[:-1]
        return None, r


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int = 0
    total_pages: int = 0
    next_cursor: int | None = None
    previous_cursor: int | None = None
