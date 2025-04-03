from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from fastapi import FastAPI, status
from fastapi.exceptions import HTTPException, RequestValidationError
from starlette.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src import logger
from src.config import app_configs, settings
from src.database import sessionmanager
from src.exceptions import BadRequest, InternalServerError, AuthenticationError
from src.core.routers.base_router import router as base_router
from src.core.routers.auth_router import router as auth_router
from src.responses import error

from src.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncGenerator:

    # Startup

    yield

    if settings.ENVIRONMENT.is_testing:
        return

    # Database
    if sessionmanager._engine is not None:
        await sessionmanager.close()


app = FastAPI(**app_configs, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGINS_REGEX,
    allow_credentials=True,
    allow_methods=("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"),
    allow_headers=settings.CORS_HEADERS,
)

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

if settings.ENVIRONMENT.is_deployed:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
    )

app.include_router(base_router)
app.include_router(auth_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exception):
    raw_errors = exception.errors()
    logger.info(f"Validation Error Occured: {raw_errors}")
    errors = [
        {
            "field": err.get("loc"),
            "message": err.get("msg"),
            "code": err.get("type").upper()
        } for err in raw_errors
    ]

    return error(errors, status.HTTP_422_UNPROCESSABLE_ENTITY)


@app.exception_handler(BadRequest)
async def bad_request_exception_handler(_, exception):
    logger.info(f"Bad Request Occured: {exception.message}")
    errors = [{"message": exception.message, "code": exception.code}]
    return error(errors, exception.status_code)


@app.exception_handler(AuthenticationError)
async def authentication_exception_handler(_, exception):
    logger.info(f"Authentication Failed: {exception.message}")
    errors = [{"message": exception.message, "code": exception.code}]
    return error(errors, exception.status_code)


@app.exception_handler(InternalServerError)
async def internal_server_error_exception_handler(_, exception):
    logger.info(f"Internal Server Error Occured: {exception.message}")
    errors = [{"message": exception.message, "code": exception.code}]
    return error(errors, exception.status_code)


@app.exception_handler(Exception)
async def exception_handler(_, exception):
    logger.error(f"Exception Occured: {exception}")
    errors = [{"message": str(exception), "code": "INTERNAL_ERROR"}]
    return error(errors, status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exception):
    logger.info(f"HTTP Error Occured: {exception.detail}")
    errors = [{"message": exception.detail, "code": "HTTP_ERROR"}]
    return error(errors, exception.status_code)
