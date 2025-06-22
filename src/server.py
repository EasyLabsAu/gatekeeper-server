import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi.applications import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import setup_routes
from core.app import App
from core.config import settings
from core.database import check_database_connection, engine
from helpers.auth import get_public_paths, public_route
from helpers.constants import USER_CREATED_EVENT
from helpers.events import events
from helpers.logger import Logger
from middlewares.auth import AuthenticateRequest
from middlewares.log_requests import LogRequests
from workers.users import on_user_created

logger = Logger(__name__)


@asynccontextmanager
async def app_lifespan(server: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    if not await check_database_connection(engine):
        raise RuntimeError("Database connection failed after retries")

    logger.info("Database connection established successfully")
    logger.info("Lifespan startup: Starting worker")
    await events.start_worker()
    logger.info("Lifespan startup: Registering event handlers")
    events.on(USER_CREATED_EVENT, on_user_created)
    yield
    logger.info("Lifespan shutdown: Stopping worker")
    await events.stop_worker()


def app_middlewares():
    cors_origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else ["*"]

    def public_paths():
        logger.info(f"Public paths: {get_public_paths(app)}")
        return get_public_paths(app)

    return [
        (
            # CORS Middleware
            CORSMiddleware,
            {
                "allow_origins": cors_origins,
                "allow_credentials": True,
                "allow_methods": ["*"],
                "allow_headers": ["*"],
            },
        ),
        (
            AuthenticateRequest,
            {"public_paths_provider": public_paths},
        ),
        (LogRequests, {}),
    ]


server = App(
    router=setup_routes(),
    lifespan=app_lifespan,
    middlewares=app_middlewares(),
)
app = server.get_app()


@app.get(
    "/health",
    response_model=dict[str, Any],
    summary="Health Check",
    description="Check the health status of the API.",
    tags=["health"],
)
@public_route
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENV,
    }
