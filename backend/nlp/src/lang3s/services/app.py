import traceback
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from lang3s import config
from lang3s.services.api.agents import router as agent_router
from lang3s.services.api.analytics import analytics_lifecycle
from lang3s.services.api.analytics import router as analytics_router
from lang3s.services.api.documents import router as documents_router
from lang3s.services.api.embeddings import router as embedding_router
from lang3s.services.api.topics import router as topic_router
from lang3s.services.api.topics import topics_lifecycle
from lang3s.services.service_logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(analytics_lifecycle(app))
        await stack.enter_async_context(topics_lifecycle(app))
        yield
    logger.info("Application shutting down...")


app = FastAPI(lifespan=lifespan)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"An unhandled error occurred: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "content": {"detail": "Internal Server Error. Please contact support."},
        },
    )


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
    current_dir = Path(__file__).parent
    reload_dir = current_dir / "src" / "lang3s"
    if not reload_dir.exists():
        reload_dirs = [str(current_dir)]
    else:
        reload_dirs = [str(reload_dir)]

    uvicorn.run(
        "lang3s.services.app:app",
        host="0.0.0.0",
        port=config.FASTAPI_PORT,
        reload=True,
        reload_dirs=reload_dirs,
    )
