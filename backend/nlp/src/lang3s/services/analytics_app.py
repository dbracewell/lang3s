import traceback
from contextlib import AsyncExitStack, asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from lang3s import config
from lang3s.services.api.analytics_api import (
    analytics_lifecycle,
)
from lang3s.services.api.analytics_api import (
    router as analytics_router,
)
from lang3s.services.api.charting_api import (
    charting_lifecycle,
)
from lang3s.services.api.charting_api import (
    router as charting_router,
)
from lang3s.utils.logger.service_logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(analytics_lifecycle(app))
        await stack.enter_async_context(charting_lifecycle(app))
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

app.include_router(analytics_router)
app.include_router(charting_router)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.FAST_API_ANALYTICS_PORT,
        # access_log=False,
    )
