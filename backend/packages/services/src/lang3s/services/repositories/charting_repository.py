import math
from typing import Any, Literal

from lang3s.core.exceptions import BadDataException
from lang3s.data.models.global_metadata import DataType
from lang3s.data.schemas.global_metadata import GlobalMetadataBySource
from lang3s.services.analytics import AnalyticsDB, template_engine
from lang3s.services.models.charting_models import (
    ChartData,
    ChartDataRequest,
    ChartResult,
    ChartSeries,
    ChartType,
    CountType,
    SeriesType,
)


class ChartingRepository:
    def __init__(self, db: AnalyticsDB):
        self.db: AnalyticsDB = db
        self.queries = template_engine

    async def get_chart_data(
        self,
        request: ChartDataRequest,
        metadata: GlobalMetadataBySource,
    ) -> ChartResult:

        request.update(metadata)
        x_total, x_template, x_params = self._build_chart_series_query(
            series=request.x,
            count_type=request.count_type,
            axis="X",
        )
        x_page = request.x.page
        x_num_pages = math.ceil(x_total / request.x.page_size)

        y_params = []
        y_total = 0
        y_page = 0
        y_num_pages = 0

        if request.y is None:
            order_by = request.x.type.get_order_by_clause(
                request.x.data_type, count_type=request.count_type
            )
            query = f"""
                                WITH
                                {x_template}
                                select 
                                text as text1, 
                                '' as text2,
                                value as value1, 
                                '' as value2,
                                COUNT(distinct document_id) as document_count,
                                COUNT(distinct sentence_id) as sentence_count,
                                COUNT() as mention_count
                                FROM X_MAPPED
                                GROUP BY text, value
                                ORDER BY {order_by}
                    """
        else:
            y_total, y_template, y_params = self._build_chart_series_query(
                series=request.y,
                count_type=request.count_type,
                axis="Y",
            )

            y_page = request.y.page
            y_num_pages = math.ceil(y_total / request.y.page_size)

            inner_join_on = "X.sentence_id = Y.sentence_id"
            if (
                request.x.type == SeriesType.DOCUMENT_METADATA
                or request.y.type == SeriesType.DOCUMENT_METADATA
            ):
                inner_join_on = "X.document_id = Y.document_id"

            query = f"""
                        WITH
                        {x_template},{y_template}
                        select X.text as text1, Y.text as text2, X.value as value1, Y.value as value2,
                        COUNT(distinct X.document_id) as document_count,
                        COUNT(distinct X.sentence_id) as sentence_count,
                        COUNT() as mention_count
                        FROM X_MAPPED as X 
                        INNER JOIN Y_MAPPED as Y on {inner_join_on}
                        GROUP BY X.text, Y.text, X.value, Y.value
                        ORDER BY X.text, Y.text, X.value, Y.value
            """

        results = (
            self.db.execute(query, x_params + y_params).df().to_dict(orient="records")
        )

        return ChartResult(
            x_total=x_total,
            y_total=y_total,
            x_next_page=x_page + 1 if x_page + 1 <= x_num_pages else None,
            x_prev_page=x_page - 1 if x_page > 0 else None,
            y_next_page=y_page + 1 if y_page + 1 <= y_num_pages else None,
            y_prev_page=y_page - 1 if y_page > 0 else None,
            x_data_type=request.x.data_type.category,
            y_data_type=request.y.data_type.category if request.y else None,
            chart_type=request.chart_type or ChartType.barchart,
            results=[
                ChartData(
                    text1=str(row["text1"]),
                    value1=row["value1"],
                    text2=str(row["text2"]),
                    value2=row["value2"],
                    documentCount=row["document_count"],
                    sentenceCount=row["sentence_count"],
                    mentionCount=row["mention_count"],
                )
                for row in results
            ],
        )

    def _get_counts_for_chart_data(self, series: ChartSeries) -> int:
        if series.type == SeriesType.ANNOTATION:
            mappings = [x.strip() for x in (series.value or "").split(",")]
            params: list[Any] = self.queries.prepare_path_params(mappings)
            total_query = self.queries.render(
                "analytics/annotation_total_unique_filtered.sql.j2",
                mapping_list=mappings,
            )
            return self.db.execute(total_query, params).fetchone()[0]
        if series.type == SeriesType.TOPIC:
            return self.db.execute("select count(*) from pg_db.topics").fetchone()[0]
        else:
            total_query_template = (
                "chart/document_metadata_total.sql.j2"
                if series.type == SeriesType.DOCUMENT_METADATA
                else "chart/annotation_metadata_total.sql.j2"
            )
            total_query = self.queries.render(
                total_query_template,
                data_type=series.data_type,
                type=series.type.source,
                formatter=series.formatter,
            )
            parameters = [series.value, f"$.{series.value}"]
            return self.db.execute(
                total_query,
                parameters=parameters,
            ).fetchone()[0]

    def _build_chart_series_query(
        self,
        series: ChartSeries,
        count_type: CountType,
        axis: Literal["X", "Y"],
    ) -> tuple[int, str, list[Any]]:
        template_name = series.type.get_series_data_template()
        template = self.queries.render(
            f"chart/{template_name}",
            VALUE_SELECTOR=f"{axis}_VALUES",
            VALUE_MAPPING=f"{axis}_MAPPED",
            DATA_SELECTOR=f"{axis}_SELECT",
            data_type=series.data_type,
            order_by=series.type.get_order_by_clause(series.data_type, count_type),
            mapping_list=[
                x.strip() for x in (series.value or "").split(",") if x.strip()
            ],
            formatter=series.formatter,
            type=series.type.source,
        )
        total = self._get_counts_for_chart_data(series)
        params = series.get_parameters()
        return total, template, params

    def shutdown(self) -> None:
        self.db.close()
