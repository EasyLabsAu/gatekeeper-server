# pyright: reportOptionalCall=false

import json
from uuid import UUID

from socketio import AsyncServer

from src.helpers.cache import Cache
from src.helpers.constants import (
    CHAT_UPDATED_EVENT,
)
from src.helpers.events import events
from src.helpers.logger import Logger
from src.helpers.model import utc_now
from src.models.chat import Chat, ChatType
from src.models.sessions import SessionCreate, SessionUpdate
from src.repositories.forms import FormRepository
from src.repositories.sessions import SessionRepository
from src.services.chatbot import Chatbot

logger = Logger(__name__)

cache = Cache(default_ttl=86400)


async def set_session_id(client_id: str, session_id: str):
    await cache.set(f"sessions:{client_id}", session_id)


async def get_session_id(client_id: str) -> str | None:
    return await cache.get(f"sessions:{client_id}")


async def delete_sessions(client_id: str):
    await cache.delete(
        f"sessions:{client_id}",
    )


async def get_transcriptions(client_id: str) -> list[dict]:
    try:
        return await cache.list_get(f"transcriptions:{client_id}") or []
    except (AttributeError, TypeError):
        await cache.delete(f"transcriptions:{client_id}")
        return []


async def set_transcriptions(client_id: str, transcriptions: list[dict]):
    key = f"transcriptions:{client_id}"
    await cache.delete(key)
    if transcriptions:
        await cache.list_append(key, *transcriptions)


async def append_transcription(client_id: str, message: dict):
    await cache.list_append(f"transcriptions:{client_id}", message)


async def delete_transcriptions(client_id: str):
    await cache.delete(
        f"transcriptions:{client_id}",
    )


async def set_form_id(client_id: str, form_id: str):
    await cache.set(f"forms:{client_id}", form_id)


async def get_form_id(client_id: str) -> str | None:
    return await cache.get(f"forms:{client_id}")


async def delete_forms(client_id: str):
    await cache.delete(
        f"forms:{client_id}",
    )


async def delete_client(client_id: str):
    client_list = await cache.list_get("clients") or []

    for i, client in enumerate(client_list):
        if client == client_id:
            client_list.pop(i)
            break

    await cache.delete("clients")

    if client_list:
        await cache.list_append("clients", *client_list)


def chat_events(sio: AsyncServer):
    if sio is not None and hasattr(sio, "on"):

        @sio.on("chat")
        async def on_chat(sid, data, auth):
            logger.info("Message from %s: %s", sid, data)
            socket_session = await sio.get_session(sid)
            client_id = (
                auth.get("client_id") if auth else socket_session.get("client_id", sid)
            )

            try:
                parsed_data = json.loads(data) if isinstance(data, str) else data
                sender = parsed_data.get("sender")
                user_message = parsed_data.get("message")
                form = parsed_data.get("form", None)

                if form:
                    await set_form_id(client_id, form)

                # TODO: delete when the chat is ended by user
                # await delete_transcriptions(client_id)
                # await delete_sessions(client_id)
                # await delete_client(client_id)

                if user_message and sender == "user":
                    transcriptions = await get_transcriptions(client_id)
                    if not transcriptions:
                        await append_transcription(
                            client_id,
                            Chat(
                                type=ChatType.ONBOARDING,
                                client_id=client_id,
                                sender="bot",
                                message="Hey there! How can I help you?",
                                timestamp=utc_now().isoformat(),
                                form=None,
                            ).model_dump(),
                        )
                    await append_transcription(
                        client_id,
                        Chat(
                            type=ChatType.ENGAGEMENT,
                            client_id=client_id,
                            sender="user",
                            message=user_message,
                            timestamp=utc_now().isoformat(),
                            form=None,
                        ).model_dump(),
                    )

                    session_id = await get_session_id(client_id)
                    session_repository = SessionRepository()

                    if not session_id:
                        current_transcriptions = await get_transcriptions(client_id)
                        session_data = SessionCreate(
                            transcription=current_transcriptions,
                            meta_data={
                                "client_fingerprint": client_id,
                                "user_agent": socket_session.get(
                                    "user_agent", "unknown"
                                ),
                                "client_ip": socket_session.get("client_ip", "unknown"),
                            },
                        )
                        result = await session_repository.create(session_data)
                        if result and result.data:
                            session_id = result.data.id
                        await set_session_id(client_id, str(session_id))
                    else:
                        await session_repository.get(UUID(session_id))

                    chatbot = Chatbot(session_id=str(session_id))
                    form_id = await get_form_id(client_id)
                    form_repository = FormRepository()
                    bot_response = await chatbot.get_response(user_message)
                    if form_id:
                        form = await form_repository.get(UUID(form_id))
                        if form and form.data:
                            form_name = form.data.name
                            await sio.emit(
                                "chat",
                                Chat(
                                    type=ChatType.ENGAGEMENT,
                                    client_id=client_id,
                                    sender="bot",
                                    message=f"Great! Let us start with {form_name}.",
                                    timestamp=utc_now().isoformat(),
                                    form=None,
                                ).model_dump(),
                                room=sid,
                            )
                            bot_response = await chatbot.get_response(
                                user_message, form.data.model_dump()
                            )
                        else:
                            bot_response = "Form not found. Please try a different one."
                            await delete_forms(client_id)

                    bot_message = Chat(
                        type=ChatType.ENGAGEMENT,
                        client_id=client_id,
                        sender="bot",
                        message=bot_response,
                        timestamp=utc_now().isoformat(),
                        form=None,
                    )
                    await append_transcription(client_id, bot_message.model_dump())

                    current_transcriptions = await get_transcriptions(client_id)
                    if session_id:
                        await events.emit(
                            CHAT_UPDATED_EVENT,
                            session_id,
                            SessionUpdate(
                                transcription=current_transcriptions,
                            ),
                        )
                    logger.info(
                        "Current transcription for %s: %s",
                        client_id,
                        current_transcriptions,
                    )
                    await sio.emit(
                        "chat",
                        bot_message.model_dump(),
                        room=sid,
                    )
                else:
                    logger.warning(
                        "Received empty 'message' from %s. Data: %s", client_id, data
                    )

            except json.JSONDecodeError:
                logger.error(
                    "Failed to parse JSON from %s. Raw data: %s", client_id, data
                )
            except (TypeError, AttributeError) as e:
                logger.exception(
                    "Unexpected error while handling chat from %s: %s", client_id, e
                )
