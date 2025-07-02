from collections.abc import Sequence
from typing import Any

import socketio
from socketio import ASGIApp, AsyncServer

from src.helpers.logger import Logger

logger = Logger(__name__)

MiddlewareSpec = tuple[type[Any], dict[str, Any]]

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True,
)


class SOCKET_SERVER:
    def __init__(
        self,
        *,
        middlewares: Sequence[MiddlewareSpec] | None = None,
    ):
        self.sio = sio
        self.app = ASGIApp(self.sio)
        if middlewares:
            for middleware_class, options in reversed(middlewares):
                self.app = middleware_class(self.app, **options)

    def gateway(self) -> ASGIApp:
        return self.app

    def get_server(self) -> AsyncServer:
        return self.sio
