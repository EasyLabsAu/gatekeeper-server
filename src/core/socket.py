from collections.abc import Sequence
from typing import Any

import socketio
from socketio import ASGIApp, AsyncServer

from src.core.config import settings
from src.helpers.constants import WEBSOCKET_API_PREFIX
from src.helpers.logger import Logger

logger = Logger(__name__)

MiddlewareSpec = tuple[type[Any], dict[str, Any]]

state_manager = socketio.AsyncRedisManager(str(settings.REDIS_URI))


class SOCKET_GATEWAY:
    def __init__(
        self,
        *,
        middlewares: Sequence[MiddlewareSpec] | None = None,
    ):
        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins=[],
            logger=True,
            engineio_logger=True,
            client_manager=state_manager,
        )
        self.asgisocket = ASGIApp(self.sio, socketio_path=WEBSOCKET_API_PREFIX)
        if middlewares:
            for middleware_class, options in reversed(middlewares):
                self.asgisocket = middleware_class(self.asgisocket, **options)

    def app(self) -> ASGIApp:
        return self.asgisocket

    def server(self) -> AsyncServer:
        return self.sio
