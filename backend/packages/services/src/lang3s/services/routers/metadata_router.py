import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from lang3s.core.logger import get_logger
from lang3s.data.repositories.metadata_repository import MetadataRepository
from lang3s.data.schemas.global_metadata import (
    GlobalMetadata,
    GlobalMetadataAvailableList,
    GlobalMetadataBySource,
    GlobalMetadataUpdate,
)
from lang3s.services.helpers import DBSessionDep, ErrorDetail

logger = get_logger(__name__)


def get_metadata_repository(session: DBSessionDep):
    return MetadataRepository(session)


type MetadataRepositoryDep = Annotated[
    MetadataRepository, Depends(get_metadata_repository)
]

metadata_router = APIRouter(
    prefix="/metadata",
    tags=["documents"],
    responses={404: {"description": "Not found"}},
)


@metadata_router.post(
    "/",
    operation_id="metadataCreate",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def metadata_create(
    item: GlobalMetadata,
    repository: MetadataRepositoryDep,
) -> None:
    await repository.add(item)


@metadata_router.get(
    "",
    operation_id="metadataGetBySource",
    responses={
        200: {"model": GlobalMetadataBySource},
        401: {"model": ErrorDetail},
    },
)
async def get_all_by_source(
    repository: MetadataRepositoryDep,
) -> GlobalMetadataBySource:
    return await repository.get_all_by_source()


@metadata_router.get(
    "/probe",
    operation_id="metadataProbe",
    responses={
        200: {"model": GlobalMetadataAvailableList},
        401: {"model": ErrorDetail},
    },
)
async def get_available(
    repository: MetadataRepositoryDep,
) -> GlobalMetadataAvailableList:
    return await repository.probe()


@metadata_router.delete(
    "/{metadata_id}",
    operation_id="metadataDelete",
    responses={
        200: {"model": bool},
        401: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def metadata_delete(
    metadata_id: uuid.UUID,
    repository: MetadataRepositoryDep,
) -> bool:
    return await repository.delete_by_id(metadata_id)


@metadata_router.put(
    "/{metadata_id}",
    operation_id="metadataUpdate",
    responses={
        200: {"model": bool},
        401: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def metadata_update(
    update: GlobalMetadataUpdate,
    repository: MetadataRepositoryDep,
) -> bool:
    return await repository.update(update)
