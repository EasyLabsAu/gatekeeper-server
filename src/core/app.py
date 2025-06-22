from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import check_database_connection, engine
from helpers.logger import Logger
from middlewares.log_requests import LogRequests

logger = Logger(__name__)

MiddlewareSpec = tuple[type[Any], dict[str, Any]]


class App:
    def __init__(
        self,
        *,
        router: APIRouter | None = None,
        lifespan: Callable[[FastAPI], AbstractAsyncContextManager[None]] | None = None,
        middlewares: Sequence[MiddlewareSpec] | None = None,
    ):
        self.logger = Logger(__name__)
        self.app = FastAPI(
            title=settings.PROJECT_NAME,
            version=settings.VERSION,
            lifespan_mode="on",
            lifespan=lifespan or self._default_lifespan,
        )

        if router:
            self.app.include_router(router)

        self._configure_middlewares(middlewares)

    def _configure_middlewares(self, middlewares: Sequence[MiddlewareSpec] | None):
        if middlewares is None:
            cors_origins = (
                settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else ["*"]
            )
            middlewares = [
                (
                    CORSMiddleware,
                    {
                        "allow_origins": cors_origins,
                        "allow_credentials": True,
                        "allow_methods": ["*"],
                        "allow_headers": ["*"],
                    },
                ),
                (LogRequests, {}),
            ]

        for middleware_class, config in middlewares:
            self.app.add_middleware(middleware_class, **config)  # type: ignore[arg-type]

    @asynccontextmanager
    async def _default_lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        if not await check_database_connection(engine):
            raise RuntimeError("Database connection failed after retries")

        self.logger.info("Database connection established successfully")
        yield

    def get_app(self) -> FastAPI:
        return self.app
