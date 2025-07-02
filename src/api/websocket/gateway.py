# pyright: reportOptionalCall=false

from socketio import AsyncServer

from src.helpers.logger import Logger

logger = Logger(__name__)


def gateway_events(sio: AsyncServer):
    if sio is not None and hasattr(sio, "on"):

        @sio.on("connect")
        async def on_connect(sid, _):
            logger.info("Client connected: %s", sid)

        @sio.on("disconnect")
        async def on_disconnect(sid):
            logger.info("Client disconnected: %s", sid)
