from typing import Annotated

from fastapi import APIRouter, Depends

from lang3s.core.logger import get_logger
from lang3s.data.repositories.topic_repository import TopicRepository
from lang3s.data.schemas.topic import TopicFrontendResult
from lang3s.services.helpers import DBSessionDep, ErrorDetail

logger = get_logger(__name__)

topic_router = APIRouter(
    prefix="/topics",
    tags=["topics"],
    responses={404: {"description": "Not found"}},
)


def get_topic_repository(session: DBSessionDep):
    return TopicRepository(session)


type TopicRepositoryDep = Annotated[
    TopicRepository,
    Depends(get_topic_repository),
]


@topic_router.get(
    "/{topic_id}",
    response_model=TopicFrontendResult,
    operation_id="topicsGetTopic",
    responses={
        200: {"model": TopicFrontendResult},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def get_topic(
    topic_id: int,
    repository: TopicRepositoryDep,
) -> TopicFrontendResult:
    return await repository.get_topic_info(topic_id)
