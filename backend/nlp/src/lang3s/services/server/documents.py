import json
import os
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lang3s import config

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    responses={404: {"description": "Not found"}},
)


class DocumentResponse(BaseModel):
    document: Dict[str, Any]


@router.get("/{doc_id}")
async def get(doc_id: str):
    doc_path = os.path.join(config.DOCUMENTS_DIR, f"{doc_id}.json")
    if not os.path.exists(doc_path):
        return JSONResponse(content="Not Found", status_code=404)
    try:
        with open(doc_path) as fp:
            return DocumentResponse(document=json.load(fp))
    except Exception as e:
        return JSONResponse(content=e, status_code=500)
