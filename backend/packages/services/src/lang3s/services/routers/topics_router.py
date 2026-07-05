from typing import Annotated

from fastapi import APIRouter, Depends

from lang3s.core.exceptions import UnauthorizedException
from lang3s.core.logger import get_logger
from lang3s.data.repositories.topic_repository import TopicRepository
from lang3s.data.schemas.topic import TopicFrontendResult
from lang3s.services.helpers import DBSessionDep, ErrorDetail
from lang3s.services.schemas.topics_api_schema import TopicGraph
from lang3s.services.security import AuthenticatedUserDep

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
    "/id/{topic_id}",
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
    user: AuthenticatedUserDep,
) -> TopicFrontendResult:
    if user is None:
        raise UnauthorizedException()
    return await repository.get_topic_info(topic_id)


@topic_router.get(
    "/graph",
    response_model=TopicGraph,
    operation_id="topicsGetTopicGraph",
    responses={
        200: {"model": TopicGraph},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def get_topic_graph(
    repository: TopicRepositoryDep,
    user: AuthenticatedUserDep,
) -> TopicGraph:
    if user is None:
        raise UnauthorizedException()
    return await repository.get_topic_map()
