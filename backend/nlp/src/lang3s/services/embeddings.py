from fastapi import APIRouter
from pydantic import BaseModel

from lang3s.models.embedder import Embedder


class EmbeddingRequest(BaseModel):
    text: str


router = APIRouter(
    prefix="/embed",
    tags=["embeddings"],
    responses={404: {"description": "Not found"}},
)

embedder = Embedder()


@router.post("/")
async def embed(request: EmbeddingRequest):
    text = request.text
    has_case = text.lower() != text and text.upper() != text
    return embedder([request.text], task="nli" if has_case else "search").sentence_embeddings[0].tolist()
