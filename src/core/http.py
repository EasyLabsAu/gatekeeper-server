from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.database import check_database_connection, engine
from src.helpers.constants import CORS_CONFIGS
from src.helpers.logger import Logger
from src.middlewares.log import LogRequests

logger = Logger(__name__)

MiddlewareSpec = tuple[type[Any], dict[str, Any]]


class HTTP_GATEWAY:
    def __init__(
        self,
        *,
        router: APIRouter | None = None,
        lifespan: Callable[[FastAPI], AbstractAsyncContextManager[None]] | None = None,
        middlewares: Sequence[MiddlewareSpec] | None = None,
    ):
        self.logger = Logger(__name__)
        self.http = FastAPI(
            title=settings.PROJECT_NAME,
            version=settings.VERSION,
            lifespan_mode="on",
            lifespan=lifespan or self._default_lifespan,
        )

        if router:
            self.http.include_router(router)

        self._configure_middlewares(middlewares)

    def _configure_middlewares(self, middlewares: Sequence[MiddlewareSpec] | None):
        if middlewares is None:
            middlewares = [
                (CORSMiddleware, CORS_CONFIGS),
                (LogRequests, {}),
            ]

        for middleware_class, config in middlewares:
            self.http.add_middleware(middleware_class, **config)  # type: ignore[arg-type]

    @asynccontextmanager
    async def _default_lifespan(self, _: FastAPI) -> AsyncGenerator[None, None]:
        print(f"Connecting to database at {settings.POSTGRES_URI}")
        if not await check_database_connection(engine):
            raise RuntimeError("Database connection failed after retries")

        self.logger.info("Database connection established successfully")
        yield

    def app(self) -> FastAPI:
        return self.http
