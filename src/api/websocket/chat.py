# pyright: reportOptionalCall=false

import json
from datetime import datetime, timezone

from socketio import AsyncServer

from src.helpers.logger import Logger
from src.services.chatbot.core import Chatbot

logger = Logger(__name__)

# Initialize chatbot instance for each session (or manage globally if state is shared)
# For simplicity, let's assume a new chatbot per session for now.
# In a real app, store and retrieve chatbots from a session manager.


def chat_events(sio: AsyncServer):
    if sio is not None and hasattr(sio, "on"):

        @sio.on("chat")
        async def on_chat(sid, data):
            logger.info("Message from %s: %s", sid, data)

            try:
                parsed_data = json.loads(data) if isinstance(data, str) else data
                sender = parsed_data.get("sender")
                user_message = parsed_data.get("message")

                if user_message and sender == "user":
                    chatbot = Chatbot(session_id=sid)
                    bot_response = chatbot.get_response(user_message)

                    await sio.emit(
                        "chat",
                        {
                            "sender": "bot",
                            "message": bot_response,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                        room=sid,
                    )
                else:
                    logger.warning(
                        "Received empty 'message' from %s. Data: %s", sid, data
                    )

            except json.JSONDecodeError:
                logger.error("Failed to parse JSON from %s. Raw data: %s", sid, data)
            except (TypeError, AttributeError) as e:
                logger.exception(
                    "Unexpected error while handling chat from %s: %s", sid, e
                )
