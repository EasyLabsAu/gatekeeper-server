from src.core.socket import SOCKET_SERVER
from src.helpers.logger import Logger

sio = SOCKET_SERVER().server()

logger = Logger(__name__)


async def on_connect(sid):
    logger.info("Client connected: %s", sid)
    await sio.emit(
        "chat_message",
        {"data": "Welcome to the chat!"},
        room=sid,
    )


async def on_disconnect(sid):
    logger.info("Client disconnected: %s", sid)


async def on_chat_message(sid, data):
    logger.info("Message from %s: %s", sid, data)
    await sio.emit(
        "chat_message",
        {"data": data},
        skip_sid=sid,
    )


sio.on(
    "connect",
    on_connect,
)
sio.on(
    "disconnect",
    on_disconnect,
)
sio.on(
    "chat_message",
    on_chat_message,
)
