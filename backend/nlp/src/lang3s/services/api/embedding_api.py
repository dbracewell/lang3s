from contextlib import asynccontextmanager

from fastapi import APIRouter

from lang3s.models.embedder import Embedder
from lang3s.services.model.embedding_models import EmbeddingRequest
from lang3s.utils.logger.service_logging import get_logger

router = APIRouter(
    prefix="/embed",
    tags=["embeddings"],
    responses={404: {"description": "Not found"}},
)

logger = get_logger(__name__)
embedder: Embedder = None  # type: ignore


@asynccontextmanager
async def embedding_lifecycle():
    logger.info("Initializing Embedding Api...")
    global embedder
    embedder = Embedder()
    yield


@router.post("/")
async def embed(request: EmbeddingRequest):
    global embedder
    text = request.text
    has_case = text.lower() != text and text.upper() != text
    return (
        embedder([request.text], task="nli" if has_case else "search")
        .sentence_embeddings[0]
        .tolist()
    )
