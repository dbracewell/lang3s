import asyncio
from contextlib import AsyncExitStack, asynccontextmanager

import uvicorn
from fastapi import FastAPI

from lang3s.core import config
from lang3s.core.logger import get_logger
from lang3s.data.db import session_manager
from lang3s.services.helpers import create_fastapi_app
from lang3s.services.routers.embedding_router import (
    embedding_lifecycle,
    embedding_router,
)
from lang3s.services.routers.jobs_router import jobs_router
from lang3s.services.routers.topics_router import topic_router

logger = get_logger("CORE_API")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lan3gs core services starting up...")
    session_manager.init()
    try:
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(embedding_lifecycle())
            yield
    except asyncio.CancelledError:
        pass
    await session_manager.close()
    logger.info("Lan3gs core services shutting down...")


app = create_fastapi_app(
    title="Lan3gs Core Services",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(jobs_router)
app.include_router(topic_router)
app.include_router(embedding_router)
# app.include_router(agent_router)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.FASTAPI_PORT,
        access_log=False,
    )
