import os
from collections.abc import AsyncGenerator

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src.core.config import settings


class Chatbot:
    def __init__(
        self,
        llm_provider: str = settings.LLM_PROVIDER,
        model_name: str = settings.LLM_MODEL,
        llm_key: str = settings.LLM_KEY,
    ):
        if llm_provider == "google_genai":
            os.environ["GOOGLE_API_KEY"] = llm_key

        self.model = init_chat_model(
            model_name,
            model_provider=llm_provider,
            model_kwargs={"streaming": True},
        )

        self.conversation_history: list[BaseMessage] = []

    def chat_response(self, user_input: str) -> str:
        self.conversation_history.append(HumanMessage(content=user_input))
        response = self.model.invoke(self.conversation_history)

        self.conversation_history.append(AIMessage(content=response.content))

        if isinstance(response.content, str):
            return response.content
        elif isinstance(response.content, list):
            return " ".join(str(item) for item in response.content)
        else:
            return str(response.content)

    async def chat_stream(self, user_input: str) -> AsyncGenerator[str, None]:
        self.conversation_history.append(HumanMessage(content=user_input))
        stream_response = self.model.astream(self.conversation_history)

        full_response = ""
        async for chunk in stream_response:
            token = self._extract_text(chunk.content)
            full_response += token
            yield token

        self.conversation_history.append(AIMessage(content=full_response))

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

    def clear_history(self):
        self.conversation_history = []

    def get_history(self) -> list[BaseMessage]:
        return self.conversation_history

    def set_system_prompt(self, system_prompt: str):
        self.conversation_history = [SystemMessage(content=system_prompt)]
