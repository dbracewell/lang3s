import os
from functools import partial
from typing import Annotated

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lang3s.core.clients import RedisAsyncClient
from lang3s.core.exceptions.custom import CodedException
from lang3s.data.db import get_db_session


async def get_redist_client():
    async with RedisAsyncClient() as client:
        yield client


type DBSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
type RedisDep = Annotated[RedisAsyncClient, Depends(get_redist_client)]


class ErrorDetail(BaseModel):
    detail: str
    code: int


def custom_openapi(app: FastAPI, title: str, version: str):
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=title,
        version=version,
        openapi_version="3.0.3",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def create_fastapi_app(
    title: str,
    version: str = "1.0.0",
    lifespan=None,
    root_path: str = "/",
    openapi_url: str = "/openapi.json",
):
    origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")

    app = FastAPI(
        root_path=root_path,
        title=title,
        version=version,
        lifespan=lifespan,
        openapi_url=openapi_url,
    )

    app.add_middleware(
        CORSMiddleware,  # type: ignore
        allow_origins=origins_env.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Content-Type", "Authorization", "Accept"],
    )

    @app.exception_handler(CodedException)
    async def global_http_exception_handler(
        request: Request,
        exc: CodedException,
    ):
        error_data = ErrorDetail(code=exc.code, detail=str(exc))
        return JSONResponse(
            status_code=exc.code,
            content=error_data.model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ):
        body = await request.body()
        error_data = ErrorDetail(code=422, detail=body.decode("utf-8"))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_data.model_dump(),
        )

    app.openapi = partial(custom_openapi, app=app, title=title, version=version)

    return app
