from typing import Annotated

from fastapi import APIRouter, Depends

from lang3s.core.exceptions import UnauthorizedException
from lang3s.data.repositories.ontology_repository import OntologyRepository
from lang3s.data.schemas.ontology import (
    AnnotationOntologyMappingList,
    IsolatedOntologyEntry,
    OntologyEntryCreationRequest,
    OntologyFrontEnd,
    OntologyNameExists,
    OntologyPaths,
    OntologyUpdateRequest,
    PotentialMappingList,
)
from lang3s.services.helpers import DBSessionDep, ErrorDetail
from lang3s.services.permissions import Permissions
from lang3s.services.security import AuthenticatedUserDep

ontology_router = APIRouter(
    prefix="/ontology",
    tags=["ontology"],
    responses={404: {"description": "Not found"}},
)


def get_ontology_repository(session: DBSessionDep):
    return OntologyRepository(session)


type OntologyRepositoryDep = Annotated[
    OntologyRepository,
    Depends(get_ontology_repository),
]


@ontology_router.get(
    "",
    response_model=OntologyFrontEnd,
    operation_id="ontologyGet",
    responses={
        200: {"model": OntologyFrontEnd},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def get_ontology(
    repository: OntologyRepositoryDep,
    user: AuthenticatedUserDep,
) -> OntologyFrontEnd:
    if user is None:
        raise UnauthorizedException()
    ontology = await repository.load_ontology()
    return OntologyFrontEnd(
        paths=list(ontology.path_to_node.keys()),
        nodes={
            o.path: IsolatedOntologyEntry(**o.model_dump(exclude={"children"}))
            for o in ontology.nodes
        },
    )


@ontology_router.get(
    "/exists/{name}",
    response_model=OntologyNameExists,
    operation_id="ontologyNameExists",
    responses={
        200: {"model": OntologyFrontEnd},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def name_exists(
    name: str,
    repository: OntologyRepositoryDep,
    user: AuthenticatedUserDep,
) -> OntologyNameExists:
    if user is None:
        raise UnauthorizedException()
    return OntologyNameExists(exists=await repository.name_exists(name))


@ontology_router.get(
    "/document/{doc_id}",
    response_model=AnnotationOntologyMappingList,
    operation_id="ontologyGetAnnotationsForDocument",
    responses={
        200: {"model": AnnotationOntologyMappingList},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def get_annotations_for_doc(
    doc_id: str,
    repository: OntologyRepositoryDep,
    user: AuthenticatedUserDep,
) -> AnnotationOntologyMappingList:
    if user is None:
        raise UnauthorizedException()
    return await repository.get_annotations_for_document(doc_id)


@ontology_router.post(
    "/update",
    operation_id="updateOntologyEntry",
    responses={
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def update_entry(
    payload: OntologyUpdateRequest,
    repository: OntologyRepositoryDep,
    user: AuthenticatedUserDep,
):
    if user is None or not user.has_permission(Permissions.ontology.edit):
        raise UnauthorizedException()
    return await repository.update_entry(payload)


@ontology_router.delete(
    "/node/{node_id}",
    operation_id="deleteOntologyEntry",
    responses={
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def delete_entry(
    node_id: int,
    repository: OntologyRepositoryDep,
    user: AuthenticatedUserDep,
):
    if user is None or not user.has_permission(Permissions.ontology.edit):
        raise UnauthorizedException()
    return await repository.delete_entry(node_id)


@ontology_router.get(
    "/node/{path}/path",
    operation_id="ontologyGetNodePath",
    response_model=OntologyPaths,
    responses={
        200: {"model": OntologyPaths},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def get_node_path(
    path: str,
    repository: OntologyRepositoryDep,
    user: AuthenticatedUserDep,
):
    if user is None:
        raise UnauthorizedException()
    return await repository.get_node_path(path)


@ontology_router.post(
    "",
    operation_id="addOntologyEntry",
    responses={
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def add_ontology_entry(
    payload: OntologyEntryCreationRequest,
    repository: OntologyRepositoryDep,
    user: AuthenticatedUserDep,
):
    if user is None or not user.has_permission(Permissions.ontology.edit):
        raise UnauthorizedException()
    return await repository.add_entry(payload)


@ontology_router.get(
    "/potential_mappings",
    operation_id="ontologyGetPotentialMappings",
    responses={
        200: {"model": PotentialMappingList},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
    },
)
async def get_potential_mappings(
    repository: OntologyRepositoryDep,
    user: AuthenticatedUserDep,
) -> PotentialMappingList:
    if user is None:
        raise UnauthorizedException()
    return await repository.get_all_potential_mappings()
