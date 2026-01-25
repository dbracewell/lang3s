import json
import os
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lang3s import config
from lang3s.data.db.filestore import FILE_STORE

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    responses={404: {"description": "Not found"}},
)


class DocumentResponse(BaseModel):
    document: Dict[str, Any]


@router.get("/{doc_id}")
async def get(doc_id: str):
    try:
        return DocumentResponse(document=FILE_STORE.read_document(doc_id).to_json())
    except Exception as e:
        return JSONResponse(content=e, status_code=500)
