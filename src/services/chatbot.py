import json
import os
from collections.abc import AsyncGenerator, Sequence
from typing import Any, Literal, TypedDict, overload

from aioredis import RedisError
from langchain.chat_models import init_chat_model
from langchain_core.exceptions import LangChainException
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    messages_from_dict,
    messages_to_dict,
)

from src.core.config import settings
from src.helpers.cache import Cache
from src.helpers.logger import Logger
from src.repositories.forms import FormRepository

logger = Logger(__name__)


class FormQuestion(TypedDict):
    id: str
    prompt: str | None
    label: str


class ChatbotResponse(TypedDict):
    type: str
    content: str
    form_id: str | None


class Chatbot:
    HISTORY_CACHE_KEY = "conversation_history"
    FORM_CONTEXT_CACHE_KEY = "form_context"
    FORM_RESPONSES_CACHE_KEY_PREFIX = "form_responses"

    def __init__(
        self,
        session_id: str,
        llm_provider: str = settings.LLM_PROVIDER,
        model_name: str = settings.LLM_MODEL,
        llm_key: str = settings.LLM_KEY,
    ):
        if not session_id:
            raise ValueError("session_id is required for Chatbot")

        if llm_provider == "google_genai":
            os.environ["GOOGLE_API_KEY"] = llm_key

        self.model = init_chat_model(
            model_name,
            model_provider=llm_provider,
        )
        self.session_id = session_id
        self.cache = Cache(key_prefix=f"chatbot:{self.session_id}")

    async def _get_conversation_history(self) -> list[BaseMessage]:
        try:
            history_dicts = await self.cache.get(self.HISTORY_CACHE_KEY)
            if history_dicts:
                return messages_from_dict(history_dicts)
        except (RedisError, LangChainException) as e:
            logger.error("Error retrieving conversation history: %s", e)
        return []

    async def _save_conversation_history(self, history: Sequence[BaseMessage]):
        try:
            history_dicts = messages_to_dict(history)
            await self.cache.set(self.HISTORY_CACHE_KEY, history_dicts)
        except (RedisError, LangChainException) as e:
            logger.error("Error saving conversation history: %s", e)

    async def add_form_context(self, form_id: str, questions: list[FormQuestion]):
        form_context = {
            "form_id": form_id,
            "questions": questions,
            "current_question_index": 0,
        }
        try:
            await self.cache.set(self.FORM_CONTEXT_CACHE_KEY, form_context)
            first_question = form_context["questions"][0]
            return first_question.get("prompt") or first_question.get("label")
        except RedisError as e:
            logger.error("Error adding form context: %s", e)
            return (
                "Sorry, I'm having trouble starting the form. Please try again later."
            )

    async def _handle_form_response(
        self, user_input: str, form_context: dict[str, Any]
    ) -> str:
        form_id = form_context["form_id"]
        current_question_index = form_context["current_question_index"]
        current_question = form_context["questions"][current_question_index]

        try:
            await self.cache.hash_set(
                f"{self.FORM_RESPONSES_CACHE_KEY_PREFIX}:{form_id}",
                str(current_question["id"]),
                user_input,
            )
        except RedisError as e:
            logger.error("Error saving form response: %s", e)
            return "Sorry, I'm having trouble saving your response. Please try again."

        form_context["current_question_index"] += 1

        if form_context["current_question_index"] < len(form_context["questions"]):
            try:
                await self.cache.set(self.FORM_CONTEXT_CACHE_KEY, form_context)
                next_question = form_context["questions"][
                    form_context["current_question_index"]
                ]
                return next_question.get("prompt") or next_question.get("label")
            except RedisError as e:
                logger.error("Error advancing to next question: %s", e)
                return "Sorry, I'm having trouble with the form. Please try again."
        else:
            try:
                await self.cache.delete(self.FORM_CONTEXT_CACHE_KEY)
                return "Thank you for completing the form."
            except RedisError as e:
                logger.error("Error completing form: %s", e)
                return "Thank you for completing the form."

    def _extract_text(self, content: str | list | dict) -> str:
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            return " ".join(
                str(item) if isinstance(item, str | int | float | dict) else ""
                for item in content
            )
        elif isinstance(content, dict):
            return str(content)
        else:
            return ""

    async def clear_history(self):
        try:
            await self.cache.delete(self.HISTORY_CACHE_KEY)
        except RedisError as e:
            logger.error("Error clearing history: %s", e)

    async def get_history(self) -> list[BaseMessage]:
        return await self._get_conversation_history()

    async def set_system_prompt(self, system_prompt: str):
        conversation_history = [SystemMessage(content=system_prompt)]
        await self._save_conversation_history(conversation_history)

    @overload
    def chat(
        self, user_input: str, stream: Literal[False] = False
    ) -> AsyncGenerator[ChatbotResponse, None]: ...

    @overload
    def chat(
        self, user_input: str, stream: Literal[True]
    ) -> AsyncGenerator[str, None]: ...

    def chat(self, user_input: str, stream: bool = False) -> AsyncGenerator[Any, None]:
        if stream:
            return self._stream(user_input)
        else:
            return self._batch(user_input)

    async def _stream(self, user_input: str) -> AsyncGenerator[str, None]:
        try:
            form_context = await self.cache.get(self.FORM_CONTEXT_CACHE_KEY)
            if form_context:
                response_content = await self._handle_form_response(
                    user_input, form_context
                )
                yield response_content
                return
        except RedisError as e:
            logger.error("Error retrieving form context: %s", e)
            yield "Sorry, I'm having trouble with the form. Please try again."
            return

        conversation_history = await self._get_conversation_history()
        conversation_history.append(HumanMessage(content=user_input))

        try:
            stream_response = self.model.astream(conversation_history)
            full_response = ""
            async for chunk in stream_response:
                token = self._extract_text(chunk.content)
                full_response += token
                yield token
            conversation_history.append(AIMessage(content=full_response))
            await self._save_conversation_history(conversation_history)
        except LangChainException as e:
            logger.error("Error getting chat response/stream: %s", e)
            yield "Sorry, I'm having trouble responding right now. Please try again later."

    async def _batch(self, user_input: str) -> AsyncGenerator[ChatbotResponse, None]:
        try:
            form_context = await self.cache.get(self.FORM_CONTEXT_CACHE_KEY)
            if form_context:
                response_content = await self._handle_form_response(
                    user_input, form_context
                )
                yield {
                    "type": "form",
                    "content": response_content,
                    "form_id": form_context.get("form_id"),
                }
                return
        except RedisError as e:
            logger.error("Error retrieving form context: %s", e)
            yield {
                "type": "chat",
                "content": "Sorry, I'm having trouble with the form. Please try again.",
                "form_id": None,
            }
            return

        # Form intent recognition (only for non-streaming initial messages)
        form_repo = FormRepository()
        forms = await form_repo.get_all()
        if forms and forms.data:
            form_list = [
                {"id": str(f.id), "name": f.name, "description": f.description}
                for f in forms.data
            ]
            prompt = f"""Given the user's message, identify if they are requesting to fill out a form.\n            User message: {user_input}\n            Available forms: {json.dumps(form_list)}\n            If a form matches, return a JSON object with the key 'form_id' and the ID of the matching form. Otherwise, return an empty JSON object."""
            try:
                response = await self.model.ainvoke([HumanMessage(content=prompt)])
                if isinstance(response.content, str):
                    response_json = json.loads(response.content)
                    if "form_id" in response_json:
                        yield {
                            "type": "form_start",
                            "content": "",
                            "form_id": response_json["form_id"],
                        }
                        return
            except (LangChainException, json.JSONDecodeError) as e:
                logger.error("Error identifying form: %s", e)

        # Regular chat logic
        conversation_history = await self._get_conversation_history()
        conversation_history.append(HumanMessage(content=user_input))

        try:
            response = await self.model.ainvoke(conversation_history)
            conversation_history.append(AIMessage(content=response.content))
            await self._save_conversation_history(conversation_history)

            content = ""
            if isinstance(response.content, str):
                content = response.content
            elif isinstance(response.content, list):
                content = " ".join(str(item) for item in response.content)
            else:
                content = str(response.content)
            yield {"type": "chat", "content": content, "form_id": None}
        except LangChainException as e:
            logger.error("Error getting chat response/stream: %s", e)
            yield {
                "type": "chat",
                "content": "Sorry, I'm having trouble responding right now. Please try again later.",
                "form_id": None,
            }
