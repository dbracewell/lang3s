from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema


class PreComputedStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Annotated[
        int | None,
        WithJsonSchema({"type": "integer", "nullable": True}),
    ] = None
    name: str
    value: dict[str, Any] = Field(default_factory=dict)
