import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request

from src.api import setup_http_routes, setup_websocket_events
from src.core.config import settings
from src.core.database import check_database_connection, engine
from src.core.http import HTTP_GATEWAY
from src.core.socket import SOCKET_GATEWAY
from src.helpers.constants import (
    CHAT_UPDATED_EVENT,
    HTTP_API_PREFIX,
    PROVIDER_CREATED_EVENT,
    WEBSOCKET_API_PREFIX,
)
from src.helpers.events import events
from src.helpers.logger import Logger
from src.helpers.model import APIError
from src.workers.chat import on_chat_updated
from src.workers.providers import on_provider_created

logger = Logger(__name__)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def setup_lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        logger.info(
            "Starting: %s, version: %s",
            settings.PROJECT_NAME,
            settings.VERSION,
        )
        logger.info(
            "Environment: %s",
            settings.ENV,
        )
        logger.info(
            "Database: %s",
            settings.POSTGRES_URI,
        )
        logger.info(
            "Cache: %s",
            settings.REDIS_URI,
        )
        logger.info(
            "CORS Origins: %s",
            settings.CORS_ORIGINS,
        )
        if not await check_database_connection(engine):
            raise RuntimeError("Database connection failed after retries")

        logger.info("Database connection established successfully")
        logger.info("Lifespan startup: Starting worker")
        await events.start_worker()
        logger.info("Lifespan startup: Registering event handlers")
        events.on(PROVIDER_CREATED_EVENT, on_provider_created)
        events.on(CHAT_UPDATED_EVENT, on_chat_updated)
        yield
        logger.info("Lifespan shutdown: Stopping worker")
        await events.stop_worker()

    http_gateway = HTTP_GATEWAY(
        router=setup_http_routes(HTTP_API_PREFIX),
        lifespan=setup_lifespan,
    )
    http_app = http_gateway.app()
    logger.info("HTTP API GATEWAY at %s", HTTP_API_PREFIX)

    socket_gateway = SOCKET_GATEWAY()
    socket_app = socket_gateway.app()
    socket_server = socket_gateway.server()

    http_app.mount(WEBSOCKET_API_PREFIX, socket_app)

    logger.info("WEBSOCKET API GATEWAY at %s", WEBSOCKET_API_PREFIX)
    setup_websocket_events(socket_server)

    @http_app.exception_handler(APIError)
    async def api_error_handler(_: Request, exc: APIError):
        return exc.response()

    @http_app.get(
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

    return http_app


app = create_app()
