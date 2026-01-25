import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lang3s import config
from lang3s.services.server.agents import router as agent_router
from lang3s.services.server.analytics import init_connection
from lang3s.services.server.analytics import router as analytics_router
from lang3s.services.server.documents import router as documents_router
from lang3s.services.server.embeddings import router as embedding_router
from lang3s.services.server.topics import init_globals
from lang3s.services.server.topics import router as topic_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")
    init_globals()
    init_connection()
    yield
    logger.info("Application shutting down...")


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # List of allowed origins
    allow_credentials=True,  # Allow cookies/auth headers
    allow_methods=["*"],  # Allow all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers (Content-Type, etc.)
)
app.include_router(topic_router)
app.include_router(embedding_router)
app.include_router(documents_router)
app.include_router(agent_router)
app.include_router(analytics_router)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.FASTAPI_PORT,
    )
