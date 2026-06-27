from typing import Annotated

from fastapi import APIRouter, Depends

from lang3s.core.logger import get_logger
from lang3s.data.repositories.text_repository import TextRepository
from lang3s.services.helpers import DBSessionDep, ErrorDetail
from lang3s.services.models.common import PaginatedQuery
from lang3s.services.models.text_models import DocumentListResponse

logger = get_logger(__name__)


def get_text_repository(session: DBSessionDep):
    return TextRepository(session)


type TextRepositoryDep = Annotated[TextRepository, Depends(get_text_repository)]
type PaginatedQueryDep = Annotated[PaginatedQuery, Depends(PaginatedQuery)]

document_router = APIRouter(
    prefix="/doc",
    tags=["documents"],
    responses={404: {"description": "Not found"}},
)


@document_router.get(
    "",
    operation_id="documentsGetAll",
    responses={
        200: {"model": DocumentListResponse},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def list_documents(
    query: PaginatedQueryDep,
    repository: TextRepositoryDep,
):
    return await repository.list_documents(query)
