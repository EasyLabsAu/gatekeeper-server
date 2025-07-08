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
from src.models.forms import (
    FormQuestionResponsesCreate,
    FormResponsesCreate,
    FormSectionResponsesCreate,
)
from src.models.sessions import SessionCreate, SessionUpdate
from src.repositories.forms import (
    FormQuestionRepository,
    FormQuestionResponseRepository,
    FormRepository,
    FormResponseRepository,
    FormSectionResponseRepository,
)
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


async def set_form_onboarded(client_id: str, onboarded: bool):
    await cache.set(f"form_onboarded:{client_id}", "true" if onboarded else "false")


async def get_form_onboarded(client_id: str) -> bool:
    status = await cache.get(f"form_onboarded:{client_id}")
    return status == "true"


async def delete_form_onboarded(client_id: str):
    await cache.delete(f"form_onboarded:{client_id}")


async def push_to_response_queue(client_id: str, message: dict):
    await cache.list_append(f"response_queue:{client_id}", message)


async def pop_from_response_queue(client_id: str) -> dict | None:
    return await cache.list_pop(f"response_queue:{client_id}")


async def delete_response_queue(client_id: str):
    await cache.delete(f"response_queue:{client_id}")


async def is_queue_processing(client_id: str) -> bool:
    return await cache.get(f"response_queue_processing:{client_id}") == "true"


async def set_queue_processing(client_id: str, status: bool):
    if status:
        await cache.set(f"response_queue_processing:{client_id}", "true", ttl=60)
    else:
        await cache.delete(f"response_queue_processing:{client_id}")


async def _process_response_queue(client_id: str, sio: AsyncServer, sid: str):
    if await is_queue_processing(client_id):
        return

    await set_queue_processing(client_id, True)
    try:
        while True:
            response = await pop_from_response_queue(client_id)
            if response:
                await sio.emit("chat", response, room=sid)
            else:
                break
    finally:
        await set_queue_processing(client_id, False)


async def delete_client(client_id: str):
    client_list = await cache.list_get("clients") or []

    for i, client in enumerate(client_list):
        if client == client_id:
            client_list.pop(i)
            break

    await cache.delete("clients")

    if client_list:
        await cache.list_append("clients", *client_list)


async def _get_or_create_session(client_id: str, socket_session: dict) -> str | None:
    """Get existing session or create a new one."""
    session_id = await get_session_id(client_id)
    session_repository = SessionRepository()

    if not session_id:
        current_transcriptions = await get_transcriptions(client_id)
        session_data = SessionCreate(
            transcription=current_transcriptions,
            meta_data={
                "client_fingerprint": client_id,
                "user_agent": socket_session.get("user_agent", "unknown"),
                "client_ip": socket_session.get("client_ip", "unknown"),
            },
        )
        result = await session_repository.create(session_data)
        if result and result.data:
            session_id = str(result.data.id)
            await set_session_id(client_id, session_id)
            return session_id
        return None
    else:
        await session_repository.get(UUID(session_id))
        return session_id


async def _get_form_response(
    client_id: str, user_message: str, chatbot: Chatbot
) -> dict | None:
    """Get response from chatbot, handling form-specific logic."""
    form_id = await get_form_id(client_id)
    if not form_id:
        return None

    form_repository = FormRepository()
    form = await form_repository.get(UUID(form_id))
    bot_response = None

    if form and form.data:
        form_onboarded = await get_form_onboarded(client_id)
        if not form_onboarded:
            await set_form_onboarded(client_id, True)
            await push_to_response_queue(
                client_id,
                Chat(
                    type=ChatType.ONBOARDING,
                    client_id=client_id,
                    sender="bot",
                    message="Great! I will require some details from you.",
                    timestamp=utc_now().isoformat(),
                    form=form_id,
                ).model_dump(),
            )
        bot_response = await chatbot.get_response(user_message, form.data)
        if bot_response.get("form") is None:
            meta_data = bot_response.get("meta_data")
            if isinstance(meta_data, dict):
                form_responses = meta_data.get("form_responses")
                if isinstance(form_responses, list) and form_responses:
                    await _create_form_responses(form_responses)
            await delete_forms(client_id)
            await delete_form_onboarded(client_id)
    else:
        bot_response = {
            "sender": "bot",
            "message": "Form not found. Please try a different one.",
            "timestamp": utc_now().isoformat(),
        }
        await delete_forms(client_id)
        await delete_form_onboarded(client_id)

    return bot_response


async def _create_form_responses(responses: list[dict]):
    if not responses:
        return

    form_id_str = responses[0].get("form_id")
    if not form_id_str:
        logger.error("Form ID not found in responses")
        return

    form_id = UUID(form_id_str)
    form_repository = FormRepository()
    form = await form_repository.get(form_id)
    if not form or not form.data:
        logger.error("Form not found: %s", form_id)
        return

    session_repository = SessionRepository()
    session_data = SessionCreate(
        transcription=[],
        meta_data={},
    )
    result = await session_repository.create(session_data)
    if not result or not result.data:
        logger.error("Failed to create session for form response")
        return

    session_id = result.data.id

    form_response_repository = FormResponseRepository()
    form_response = await form_response_repository.create(
        FormResponsesCreate(
            form_id=form_id, session_id=session_id, submitted_at=utc_now()
        )
    )

    if not form_response or not form_response.data:
        logger.error("Failed to create form response")
        return

    section_responses = {}
    form_question_repository = FormQuestionRepository()
    form_section_response_repository = FormSectionResponseRepository()
    form_question_response_repository = FormQuestionResponseRepository()

    for response_item in responses:
        question_id = UUID(response_item["question_id"])
        answer = response_item["answer"]

        question = await form_question_repository.get(question_id)
        if not question or not question.data:
            logger.warning("Question not found: %s", question_id)
            continue

        section_id = question.data.section_id
        if section_id not in section_responses:
            section_response = await form_section_response_repository.create(
                FormSectionResponsesCreate(
                    response_id=form_response.data.id, section_id=section_id
                )
            )
            if not section_response or not section_response.data:
                logger.error("Failed to create section response")
                continue
            section_responses[section_id] = section_response.data.id

        await form_question_response_repository.create(
            FormQuestionResponsesCreate(
                section_response_id=section_responses[section_id],
                question_id=question_id,
                answer=answer,
                submitted_at=utc_now(),
            )
        )


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
                        ).model_dump(),
                    )

                    session_id = await _get_or_create_session(client_id, socket_session)

                    if not session_id:
                        logger.error(
                            "Failed to get or create session for client %s", client_id
                        )
                        await push_to_response_queue(
                            client_id,
                            Chat(
                                type=ChatType.ENGAGEMENT,
                                client_id=client_id,
                                sender="bot",
                                message="Sorry, I'm having trouble with our session. Please try again later.",
                                timestamp=utc_now().isoformat(),
                            ).model_dump(),
                        )
                        await _process_response_queue(client_id, sio, sid)
                        return

                    chatbot = Chatbot(session_id=session_id)
                    bot_response = await _get_form_response(
                        client_id, user_message, chatbot
                    )

                    if not bot_response:
                        bot_response = await chatbot.get_response(user_message)

                    bot_message = Chat(
                        type=ChatType.ENGAGEMENT,
                        client_id=client_id,
                        sender=str(bot_response.get("sender"))
                        if bot_response.get("sender")
                        else "bot",
                        message=str(bot_response.get("message"))
                        if bot_response.get("message")
                        else "Error",
                        timestamp=str(bot_response.get("timestamp"))
                        if bot_response.get("timestamp")
                        else utc_now().isoformat(),
                        form=str(bot_response.get("form"))
                        if bot_response.get("form")
                        else None,
                    )

                    await append_transcription(
                        client_id,
                        bot_message.model_dump(),
                    )

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
                    await push_to_response_queue(client_id, bot_message.model_dump())
                    await _process_response_queue(client_id, sio, sid)
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
