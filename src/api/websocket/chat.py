# pyright: reportOptionalCall=false

import json
from datetime import datetime, timezone

from socketio import AsyncServer

from src.helpers.constants import (
    CHAT_UPDATED_EVENT,
)
from src.helpers.events import events
from src.helpers.logger import Logger
from src.models.sessions import SessionCreate, SessionUpdate
from src.repositories.sessions import SessionRepository
from src.services.chatbot.core import Chatbot

logger = Logger(__name__)

# In-memory storage for transcriptions and session IDs
transcriptions = {}
# To store sid -> session_id mapping
session_map = {}


def chat_events(sio: AsyncServer):
    if sio is not None and hasattr(sio, "on"):

        @sio.on("chat")
        async def on_chat(sid, data):
            logger.info("Message from %s: %s", sid, data)
            socket_session = await sio.get_session(sid)

            try:
                parsed_data = json.loads(data) if isinstance(data, str) else data
                sender = parsed_data.get("sender")
                user_message = parsed_data.get("message")

                if user_message and sender == "user":
                    if sid not in transcriptions:
                        transcriptions[sid] = []
                    transcriptions[sid].append(
                        {
                            "sender": sender,
                            "message": user_message,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )

                    repository = SessionRepository()
                    session_id = session_map.get(sid)

                    if not session_id:
                        session_data = SessionCreate(
                            transcription=transcriptions[sid],
                            meta_data={
                                "user_agent": socket_session.get(
                                    "user_agent", "unknown"
                                ),
                                "client_ip": socket_session.get("client_ip", "unknown"),
                            },
                        )
                        result = await repository.create(session_data)
                        if result and result.data:
                            session_id = result.data.id
                        session_map[sid] = session_id
                    else:
                        await repository.get(session_id)

                    chatbot = Chatbot(session_id=session_map[sid])
                    bot_response = await chatbot.get_response(user_message)
                    response = {
                        "sender": "bot",
                        "message": bot_response,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    transcriptions[sid].append(response)

                    if session_id:
                        await events.emit(
                            CHAT_UPDATED_EVENT,
                            session_id,
                            SessionUpdate(
                                transcription=transcriptions[sid],
                            ),
                        )
                    logger.info(
                        "Current transcription for %s: %s", sid, transcriptions[sid]
                    )
                    await sio.emit(
                        "chat",
                        response,
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
