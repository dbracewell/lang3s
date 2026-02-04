from enum import StrEnum
from typing import Any, List, Literal

from pydantic import BaseModel, Field

from lang3s.data.db.query_template import QueryTemplateEngine


class SeriesType(StrEnum):
    TOPIC = "TOPIC"
    ANNOTATION = "ANNOTATION"
    DOCUMENT_METADATA = "DOCUMENT_METADATA"
    SENTENCE_METADATA = "SENTENCE_METADATA"
    ANNOTATION_METADATA = "ANNOTATION_METADATA"

    @property
    def source(self) -> Literal["document", "sentence", "annotation"]:
        if self == SeriesType.SENTENCE_METADATA:
            return "sentence"
        if self == SeriesType.DOCUMENT_METADATA or self == SeriesType.TOPIC:
            return "document"
        return "annotation"

    def get_order_by_clause(
        self, data_type: str, count_type: Literal["document", "sentence", "mention"]
    ):
        if self == SeriesType.ANNOTATION or self == SeriesType.TOPIC:
            return f"{count_type}_count DESC"
        else:
            if data_type == "date" or data_type == "int" or data_type == "float":
                return "text"
            else:
                return "document_count DESC"

    def get_series_data_template(self):
        if self == SeriesType.DOCUMENT_METADATA:
            return "document_metadata.sql.j2"
        if self == SeriesType.TOPIC:
            return "topic.sql.j2"
        if self == SeriesType.ANNOTATION_METADATA:
            return "annotation_metadata.sql.j2"
        if self == SeriesType.SENTENCE_METADATA:
            return "annotation_metadata.sql.j2"
        if self == SeriesType.ANNOTATION:
            return "annotation.sql.j2"
        raise ValueError("Unknown SeriesType")


class ChartSeries(BaseModel):
    type: SeriesType
    value: str
    formatter: str | None = Field(default=None)
    page: int
    page_size: int
    data_type: Literal[
        "string",
        "string[]",
        "int",
        "float",
        "boolean",
        "date",
    ] = Field(default="string")

    def get_parameters(self):
        params: list[Any] = []
        if self.type in (
            SeriesType.DOCUMENT_METADATA,
            SeriesType.SENTENCE_METADATA,
            SeriesType.ANNOTATION_METADATA,
        ):
            params.extend([self.value, f"$.{self.value}"])
        if self.type == SeriesType.ANNOTATION:
            params.extend(
                QueryTemplateEngine().prepare_path_params(
                    [x.strip() for x in self.value.split(",") if x.strip()]
                )
            )
        params.extend([(self.page - 1) * self.page_size, self.page_size])
        return params


class ChartDataRequest(BaseModel):
    chart_type: str
    count_type: Literal["document", "sentence", "mention"]
    x: ChartSeries
    y: ChartSeries | None = Field(default=None)


class ChartData(BaseModel):
    text1: str
    value1: str | int | float
    documentCount: int
    sentenceCount: int
    mentionCount: int
    text2: str = Field(default="")
    value2: str | int | float = Field(default="")


class ChartResult(BaseModel):
    x_total: int
    results: list[ChartData]
    y_total: int = Field(default=0)
    x_next_page: int | None = Field(default=None)
    y_next_page: int | None = Field(default=None)
    x_prev_page: int | None = Field(default=None)
    y_prev_page: int | None = Field(default=None)
