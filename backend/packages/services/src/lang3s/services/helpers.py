from functools import partial

from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from lang3s.core.exceptions.custom import CodedException


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
):
    if cors_origins is None:
        cors_origins = ["*"]

    app = FastAPI(
        title=title,
        version=version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,  # type: ignore
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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

    app.openapi = partial(custom_openapi, app=app, title=title, version=version)

    return app
