from src.core.socket import sio
from src.helpers.logger import Logger

logger = Logger(__name__)


async def on_connect(sid):
    logger.info(f"Client connected: {sid}")
    await sio.emit(
        "chat_message", {"data": "Welcome to the chat!"}, room=sid, namespace="/chat"
    )


async def on_disconnect(sid):
    logger.info(f"Client disconnected: {sid}")


async def on_chat_message(sid, data):
    logger.info(f"Message from {sid}: {data}")
    await sio.emit("chat_message", {"data": data}, skip_sid=sid, namespace="/chat")


sio.on("connect", on_connect, namespace="/chat")
sio.on("disconnect", on_disconnect, namespace="/chat")
sio.on("chat_message", on_chat_message, namespace="/chat")
