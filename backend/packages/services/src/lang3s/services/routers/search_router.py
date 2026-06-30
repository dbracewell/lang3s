from typing import Annotated

from fastapi import APIRouter, Depends

from lang3s.services.helpers import DBSessionDep, ErrorDetail
from lang3s.services.repositories.search_repository import (
    SearchRepository,
    get_instance,
)
from lang3s.services.schemas.search_api_schema import (
    AnnotationSearchResults,
    DocumentSearchResults,
    SearchParams,
    TopicSearchResults,
)


def get_search_repository(session: DBSessionDep):
    return get_instance(session)


type SearchRepositoryDep = Annotated[SearchRepository, Depends(get_search_repository)]


search_router = APIRouter(
    prefix="/search",
    tags=["search"],
    responses={404: {"description": "Not found"}},
)


@search_router.post(
    "/docs",
    operation_id="searchDocuments",
    response_model=DocumentSearchResults,
    responses={
        200: {"model": DocumentSearchResults},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def search_documents(query: SearchParams, repository: SearchRepositoryDep):
    return await repository.search_documents(query)


@search_router.post(
    "/topics",
    operation_id="searchTopics",
    response_model=TopicSearchResults,
    responses={
        200: {"model": TopicSearchResults},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def search_topics(query: SearchParams, repository: SearchRepositoryDep):
    return await repository.search_topics(query)


@search_router.post(
    "/annotations",
    operation_id="searchAnnotations",
    response_model=AnnotationSearchResults,
    responses={
        200: {"model": AnnotationSearchResults},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def search_annotations(query: SearchParams, repository: SearchRepositoryDep):
    return await repository.search_annotations(query)
