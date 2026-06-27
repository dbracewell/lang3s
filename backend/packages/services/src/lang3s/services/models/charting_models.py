import enum
from typing import Annotated, Any

from pydantic import BaseModel, Field, WithJsonSchema

from lang3s.core.exceptions import BadDataException
from lang3s.data.models.global_metadata import DataCategory, DataType, MetadataSource
from lang3s.data.schemas.global_metadata import GlobalMetadataBySource
from lang3s.services.analytics import template_engine


class CountType(enum.StrEnum):
    document = "document"
    sentence = "sentence"
    mention = "mention"


class SeriesType(enum.StrEnum):
    TOPIC = "TOPIC"
    ANNOTATION = "ANNOTATION"
    DOCUMENT_METADATA = "DOCUMENT_METADATA"
    SENTENCE_METADATA = "SENTENCE_METADATA"
    ANNOTATION_METADATA = "ANNOTATION_METADATA"

    @property
    def source(self) -> MetadataSource:
        match self:
            case SeriesType.SENTENCE_METADATA:
                return MetadataSource.sentence
            case SeriesType.DOCUMENT_METADATA | SeriesType.TOPIC:
                return MetadataSource.document
        return MetadataSource.annotation

    def get_order_by_clause(
        self,
        data_type: DataType,
        count_type: CountType,
    ):
        if self == SeriesType.ANNOTATION or self == SeriesType.TOPIC:
            return f"{count_type}_count DESC"
        elif data_type in (DataType.date, DataType.int, DataType.float):
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
    data_type: DataType = Field(default="string")

    def update(self, metadata: GlobalMetadataBySource):
        self.page_size = max(10, self.page_size)
        self.page = max(0, self.page)
        self.data_type = DataType(self.data_type)
        if self.type == SeriesType.ANNOTATION_METADATA:
            if self.type.value in metadata.annotations:
                self.type = metadata.annotations[self.type.value].data_type
                self.formatter = metadata.annotations[self.type.value].formatter
            else:
                raise BadDataException()
        if self.type == SeriesType.DOCUMENT_METADATA:
            if self.type.value in metadata.documents:
                self.type = metadata.documents[self.type.value].data_type
                self.formatter = metadata.documents[self.type.value].formatter
            else:
                raise BadDataException()
        if self.type == SeriesType.SENTENCE_METADATA:
            if self.type.value in metadata.sentences:
                self.type = metadata.sentences[self.type.value].data_type
                self.formatter = metadata.sentences[self.type.value].formatter
            else:
                raise BadDataException()

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
                template_engine.prepare_path_params(
                    [x.strip() for x in self.value.split(",") if x.strip()]
                )
            )
        params.extend([(self.page - 1) * self.page_size, self.page_size])
        return params


class ChartType(enum.StrEnum):
    barchart = "barchart"
    heatmap = "heatmap"
    linechart = "linechart"
    scatterplot = "scatterplot"


class ChartDataRequest(BaseModel):
    chart_type: Annotated[
        ChartType | None,
        WithJsonSchema(
            {
                "type": "string",
                "nullable": True,
            }
        ),
    ] = None
    count_type: CountType
    x: ChartSeries
    y: ChartSeries | None = None

    def update(self, metadata: GlobalMetadataBySource):
        self.x.update(metadata)
        if self.y:
            self.y.update(metadata)
        if not self.chart_type:
            x_cat = DataType(self.x.data_type).category
            y_cat = DataType(self.x.data_type).category if self.y else DataCategory.none
            match x_cat:
                case DataCategory.string | DataCategory.boolean:
                    match y_cat:
                        case DataCategory.none:
                            self.chart_type = ChartType.barchart
                        case DataCategory.string | DataCategory.boolean:
                            self.chart_type = ChartType.heatmap
                        case DataCategory.number | DataCategory.date:
                            self.chart_type = ChartType.linechart
                case DataCategory.number | DataCategory.date:
                    match y_cat:
                        case (
                            DataCategory.none
                            | DataCategory.string
                            | DataCategory.boolean
                        ):
                            self.chart_type = ChartType.linechart
                        case DataCategory.number | DataCategory.date:
                            self.chart_type = ChartType.scatterplot


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
    chart_type: ChartType
    x_data_type: DataCategory
    y_data_type: DataCategory | None
    x_next_page: int | None = Field(default=None)
    y_next_page: int | None = Field(default=None)
    x_prev_page: int | None = Field(default=None)
    y_prev_page: int | None = Field(default=None)
