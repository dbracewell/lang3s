from contextlib import asynccontextmanager

from fastapi import APIRouter

from lang3s.core.logger import get_logger
from lang3s.nlp.components.embedder import Embedder
from lang3s.services.models.embedding_models import EmbeddingRequest

embedding_router = APIRouter(
    prefix="/embed",
    tags=["embeddings"],
    responses={404: {"description": "Not found"}},
)

logger = get_logger("EMBEDDING")
embedder: Embedder = None  # type: ignore


@asynccontextmanager
async def embedding_lifecycle():
    logger.info("Initializing Embedding Api...")
    global embedder
    embedder = Embedder()
    yield


@embedding_router.post("/")
async def embed(request: EmbeddingRequest):
    global embedder
    text = request.text
    has_case = text.lower() != text and text.upper() != text
    return (
        embedder([request.text], task="nli" if has_case else "search")
        .sentence_embeddings[0]
        .tolist()
    )
