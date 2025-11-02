from fastapi import APIRouter
from pydantic import BaseModel

from lang3s.nlp.embedder import Embedder


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
    print(request.text)
    return embedder([request.text])[0]
