from fastapi import APIRouter, Depends, status

from lang3s.core.logger import get_logger
from lang3s.data.repositories.metadata_repository import MetadataRepository
from lang3s.services.analytics import get_analytics_db
from lang3s.services.helpers import DBSessionDep, ErrorDetail
from lang3s.services.models.charting_models import ChartDataRequest, ChartResult
from lang3s.services.repositories.charting_repository import ChartingRepository

logger = get_logger(__name__)

charting_router = APIRouter(
    prefix="/charts",
    tags=["charts"],
    responses={404: {"description": "Not found"}},
)


def get_charting_repository() -> ChartingRepository:
    return ChartingRepository(get_analytics_db())


def get_metadata_repository(session: DBSessionDep) -> MetadataRepository:
    return MetadataRepository(session)


@charting_router.post(
    "",
    status_code=status.HTTP_200_OK,
    operation_id="analyticsGetChartData",
    responses={
        200: {"model": ChartResult},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def chart_data(
    payload: ChartDataRequest,
    charting_repository: ChartingRepository = Depends(get_charting_repository),
    metadata_repository: MetadataRepository = Depends(get_metadata_repository),
) -> ChartResult:
    metadata = await metadata_repository.get_all_by_source()
    return await charting_repository.get_chart_data(payload, metadata)
