from functools import partial
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from lang3s.core.exceptions.custom import CodedException
from lang3s.data.db import get_db_session

type DBSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


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
    cors_origins: list[str] | None = None,
    root_path: str = "/",
    openapi_url: str = "/openapi.json",
):
    if cors_origins is None:
        cors_origins = ["*"]

    app = FastAPI(
        root_path=root_path,
        title=title,
        version=version,
        lifespan=lifespan,
        openapi_url=openapi_url,
    )

    app.add_middleware(
        CORSMiddleware,  # type: ignore
        allow_origins=["http://localhost:3000"],
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

    @app.exception_handler(ValidationError)
    async def global_validation_exception_handler(
        request: Request,
        exc: ValidationError,
    ):
        error_data = ErrorDetail(code=400, detail=str(exc))
        return JSONResponse(
            status_code=400,
            content=error_data.model_dump(),
        )

    app.openapi = partial(custom_openapi, app=app, title=title, version=version)

    return app
