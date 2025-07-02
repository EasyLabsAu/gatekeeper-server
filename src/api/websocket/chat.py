from socketio import AsyncServer

from src.helpers.logger import Logger

logger = Logger(__name__)


def chat_events(sio: AsyncServer):
    @sio.on("chat")
    async def on_chat_message(sid, data):
        logger.info("Message from %s: %s", sid, data)
        await sio.emit(
            "chat_message",
            {"data": data},
            skip_sid=sid,
        )
