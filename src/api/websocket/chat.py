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


async def append_transcription(client_id: str, message: dict):
    await cache.list_append(f"transcriptions:{client_id}", message)


async def set_form_id(client_id: str, form_id: str):
    await cache.set(f"forms:{client_id}", form_id)


async def get_form_id(client_id: str) -> str | None:
    return await cache.get(f"forms:{client_id}")


async def delete_forms(client_id: str):
    await cache.delete(
        f"forms:{client_id}",
    )


async def push_to_response_queue(client_id: str, message: dict):
    await cache.list_append(f"response_queue:{client_id}", message)


async def pop_from_response_queue(client_id: str) -> dict | None:
    return await cache.list_pop(f"response_queue:{client_id}")


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


async def _get_or_create_session(client_id: str, socket_session: dict) -> str | None:
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


async def _create_form_responses(
    form_id_str: str, session_id_str: str, responses: dict[str, str]
):
    if not responses:
        return

    form_id = UUID(form_id_str)
    session_id = UUID(session_id_str)

    form_response_repository = FormResponseRepository()
    form_response = await form_response_repository.create(
        FormResponsesCreate(
            form_id=form_id, session_id=session_id, submitted_at=utc_now()
        )
    )

    if not form_response or not form_response.data:
        logger.error("Failed to create form response")
        return

    section_responses: dict[UUID, UUID] = {}
    form_question_repository = FormQuestionRepository()
    form_section_response_repository = FormSectionResponseRepository()
    form_question_response_repository = FormQuestionResponseRepository()

    for question_id_str, answer in responses.items():
        question_id = UUID(question_id_str)

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

                if user_message and sender == "user":
                    transcriptions = await get_transcriptions(client_id)
                    if not transcriptions:
                        await push_to_response_queue(
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
                    full_bot_response = ""
                    form_id_for_completion = None

                    async for chunk in chatbot.chat(user_message, stream=True):
                        if isinstance(chunk, str):
                            full_bot_response += chunk
                            await sio.emit(
                                "chat",
                                Chat(
                                    type=ChatType.ENGAGEMENT,
                                    client_id=client_id,
                                    sender="bot",
                                    message=chunk,
                                    timestamp=utc_now().isoformat(),
                                ).model_dump(),
                                to=sid,
                            )
                        elif isinstance(chunk, dict):
                            if chunk["type"] == "form_start":
                                form_id_for_completion = chunk["form_id"]
                                await set_form_id(client_id, form_id_for_completion)
                                form_repo = FormRepository()
                                form_data = await form_repo.get(
                                    UUID(form_id_for_completion)
                                )
                                if form_data and form_data.data:
                                    questions = []
                                    for section in form_data.data.sections:
                                        for q in section.questions:
                                            questions.append(
                                                {
                                                    "id": str(q.id),
                                                    "prompt": q.prompt,
                                                    "label": q.label,
                                                }
                                            )
                                    first_question_text = (
                                        await chatbot.add_form_context(
                                            form_id_for_completion, questions
                                        )
                                    )
                                    await push_to_response_queue(
                                        client_id,
                                        Chat(
                                            type=ChatType.ONBOARDING,
                                            client_id=client_id,
                                            sender="bot",
                                            message="Great! I will require some details from you.",
                                            timestamp=utc_now().isoformat(),
                                            form=form_id_for_completion,
                                        ).model_dump(),
                                    )
                                    await sio.emit(
                                        "chat",
                                        Chat(
                                            type=ChatType.ENGAGEMENT,
                                            client_id=client_id,
                                            sender="bot",
                                            message=first_question_text,
                                            timestamp=utc_now().isoformat(),
                                        ).model_dump(),
                                        to=sid,
                                    )
                                    full_bot_response = first_question_text
                                else:
                                    error_message = "Sorry, I couldn't find that form."
                                    await sio.emit(
                                        "chat",
                                        Chat(
                                            type=ChatType.ENGAGEMENT,
                                            client_id=client_id,
                                            sender="bot",
                                            message=error_message,
                                            timestamp=utc_now().isoformat(),
                                        ).model_dump(),
                                        to=sid,
                                    )
                                    await delete_forms(client_id)
                                    full_bot_response = error_message

                            elif (
                                chunk["content"] == "Thank you for completing the form."
                            ):
                                form_id_for_completion = chunk["form_id"]
                                if form_id_for_completion:
                                    form_responses = await chatbot.cache.hash_get_all(
                                        f"{chatbot.FORM_RESPONSES_CACHE_KEY_PREFIX}:{form_id_for_completion}"
                                    )
                                    if form_responses:
                                        await _create_form_responses(
                                            form_id_for_completion,
                                            session_id,
                                            form_responses,
                                        )
                                    await delete_forms(client_id)
                                await push_to_response_queue(
                                    client_id,
                                    Chat(
                                        type=ChatType.OFFBOARDING,
                                        client_id=client_id,
                                        sender="bot",
                                        message="Is there anything else I can help you with?",
                                        timestamp=utc_now().isoformat(),
                                    ).model_dump(),
                                )
                                full_bot_response = chunk["content"]
                    if full_bot_response:
                        await append_transcription(
                            client_id,
                            Chat(
                                type=ChatType.ENGAGEMENT,
                                client_id=client_id,
                                sender="bot",
                                message=full_bot_response,
                                timestamp=utc_now().isoformat(),
                            ).model_dump(),
                        )

                    current_transcriptions = await get_transcriptions(client_id)
                    await events.emit(
                        CHAT_UPDATED_EVENT,
                        session_id,
                        SessionUpdate(
                            transcription=current_transcriptions,
                        ),
                    )
                    await _process_response_queue(client_id, sio, sid)

            except Exception as e:
                logger.exception(
                    "Unexpected error while handling chat from %s: %s", client_id, e
                )
