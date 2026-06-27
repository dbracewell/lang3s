from typing import Annotated

from fastapi import APIRouter, Depends

from lang3s.data.repositories.precomputed_stats_repository import (
    PreComputedStatsRepository,
)
from lang3s.data.schemas.precomputed_stats import PreComputedStats
from lang3s.services.helpers import DBSessionDep, ErrorDetail


def get_precomputed_stas_repository(session: DBSessionDep):
    return PreComputedStatsRepository(session)


type PreComputedStatsRepositoryDep = Annotated[
    PreComputedStatsRepository, Depends(get_precomputed_stas_repository)
]

stats_router = APIRouter(
    prefix="/stats",
    tags=["stats"],
    responses={404: {"description": "Not found"}},
)


@stats_router.get(
    "/{name}",
    operation_id="precomputedStatsGetByName",
    responses={
        200: {"model": PreComputedStats},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def get_by_name(
    name: str,
    repository: PreComputedStatsRepositoryDep,
) -> PreComputedStats:
    return await repository.get_by_name(name)
