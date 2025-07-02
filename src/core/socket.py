from collections.abc import Sequence
from typing import Any

import socketio
from socketio import ASGIApp, AsyncServer

from src.core.config import settings
from src.helpers.constants import WEBSOCKET_API_PREFIX, cors_origins
from src.helpers.logger import Logger

logger = Logger(__name__)

MiddlewareSpec = tuple[type[Any], dict[str, Any]]


class SOCKET_SERVER:
    def __init__(
        self,
        *,
        middlewares: Sequence[MiddlewareSpec] | None = None,
    ):
        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_credentials=True,
            cors_allowed_origins=settings.CORS_ORIGINS
            if settings.CORS_ORIGINS == "*"
            else cors_origins,
            logger=True,
            engineio_logger=True,
        )
        self.asgisocket = ASGIApp(self.sio, socketio_path=WEBSOCKET_API_PREFIX)
        if middlewares:
            for middleware_class, options in reversed(middlewares):
                self.asgisocket = middleware_class(self.asgisocket, **options)

    def app(self) -> ASGIApp:
        return self.asgisocket

    def server(self) -> AsyncServer:
        return self.sio
