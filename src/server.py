import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi.applications import FastAPI
from fastapi.requests import Request

from src.api import setup_routes
from src.core.app import App
from src.core.config import settings
from src.core.database import check_database_connection, engine
from src.helpers.constants import PROVIDER_CREATED_EVENT
from src.helpers.events import events
from src.helpers.logger import Logger
from src.helpers.model import APIError
from src.workers.providers import on_provider_created

logger = Logger(__name__)


@asynccontextmanager
async def setup_lifespan(server: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "Starting %s, version %s in %s environment with database at %s",
        settings.PROJECT_NAME,
        settings.VERSION,
        settings.ENV,
        settings.POSTGRES_URI,
    )
    if not await check_database_connection(engine):
        raise RuntimeError("Database connection failed after retries")

    logger.info("Database connection established successfully")
    logger.info("Lifespan startup: Starting worker")
    await events.start_worker()
    logger.info("Lifespan startup: Registering event handlers")
    events.on(PROVIDER_CREATED_EVENT, on_provider_created)
    yield
    logger.info("Lifespan shutdown: Stopping worker")
    await events.stop_worker()


server = App(
    router=setup_routes(),
    lifespan=setup_lifespan,
)
app = server.get_app()


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    return exc.response()


@app.get(
    "/health",
    response_model=dict[str, Any],
    summary="Health Check",
    description="Check the health status of the API.",
    tags=["health"],
)
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "repository": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENV,
    }
