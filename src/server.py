import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request

from src.api import setup_http_routes
from src.core.config import settings
from src.core.database import check_database_connection, engine
from src.core.http import HTTP_SERVER
from src.core.socket import SOCKET_SERVER
from src.helpers.constants import (
    HTTP_API_PREFIX,
    PROVIDER_CREATED_EVENT,
    WEBSOCKET_API_PREFIX,
)
from src.helpers.events import events
from src.helpers.logger import Logger
from src.helpers.model import APIError
from src.workers.providers import on_provider_created

logger = Logger(__name__)


def create_app() -> FastAPI:
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

    http_server = HTTP_SERVER(
        router=setup_http_routes(HTTP_API_PREFIX),
        lifespan=setup_lifespan,
    )
    http_gateway = http_server.gateway()
    logger.info("HTTP API GATEWAY at %s", HTTP_API_PREFIX)

    @http_gateway.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        return exc.response()

    @http_gateway.get(
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

    socket_server = SOCKET_SERVER()
    http_gateway.mount(WEBSOCKET_API_PREFIX, socket_server.gateway())
    logger.info("WEBSOCKET API GATEWAY at %s", WEBSOCKET_API_PREFIX)
    return http_gateway


app = create_app()
