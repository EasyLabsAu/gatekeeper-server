import json
import os
import re
from collections.abc import AsyncGenerator, Sequence
from typing import Any, TypedDict
from uuid import UUID

from aioredis import RedisError
from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.exceptions import LangChainException
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    messages_from_dict,
    messages_to_dict,
)
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGEngine
from langchain_postgres.v2.async_vectorstore import AsyncPGVectorStore

from src.core.config import settings
from src.helpers.cache import Cache
from src.helpers.logger import Logger
from src.helpers.model import APIError
from src.models.contexts import ContextCategory, Contexts
from src.models.forms import FormQuery, FormQuestions, Forms, FormSections
from src.repositories.contexts import ContextRepository
from src.repositories.forms import FormRepository

logger = Logger(__name__)


class ChatbotError(Exception):
    """Base exception for chatbot errors"""

    pass


class FormNotFoundError(ChatbotError):
    """Raised when a form is not found"""

    pass


class VectorSearchError(ChatbotError):
    """Raised when vector search fails"""

    pass


class FormQuestion(TypedDict):
    id: str
    prompt: str | None
    label: str


class ChatbotResponse(TypedDict):
    flow: str
    content: str
    form_id: str | None


class Chatbot:
    HISTORY_CACHE_KEY = "conversation_history"
    FORM_CONTEXT_CACHE_KEY = "form_context"
    FORM_RESPONSES_CACHE_KEY_PREFIX = "form_responses"
    SYSTEM_PROMPT_CACHE_KEY = "system_prompt"
    FORM_INDEX_CACHE_KEY = "form_index"

    def __init__(
        self,
        session_id: str,
        llm_provider: str = settings.LLM_PROVIDER,
        model_name: str = settings.LLM_MODEL,
        llm_key: str = settings.LLM_KEY,
        embedding_model: str = settings.LLM_EMBEDDING_MODEL,
    ):
        if not session_id:
            raise ValueError("session_id is required for Chatbot")

        if llm_provider == "google_genai":
            os.environ["GOOGLE_API_KEY"] = llm_key
        else:
            raise ValueError(f"Unsupported LLM provider: {llm_provider}")

        self.model = init_chat_model(
            model_name,
            model_provider=llm_provider,
        )
        self.session_id = session_id
        self.cache = Cache(key_prefix=f"chatbot:{self.session_id}")
        self.embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model)
        self.engine: PGEngine | None = None
        self.vector_store: AsyncPGVectorStore | None = None
        self.form_vector_store: AsyncPGVectorStore | None = None
        self.context_retriever: Any = None
        self.context_repo = ContextRepository()
        self.form_repo = FormRepository()
        self.system_prompt: str | None = None
        self.rag_chain: Any = None

    async def initialize(self):
        self.engine = PGEngine.from_connection_string(url=str(settings.POSTGRES_URI))
        self.vector_store = await AsyncPGVectorStore.create(
            engine=self.engine,
            table_name=str(Contexts.__tablename__),
            embedding_service=self.embeddings,
            id_column="id",
            content_column="data",
        )
        self.form_vector_store = await AsyncPGVectorStore.create(
            engine=self.engine,
            table_name=str(Forms.__tablename__),
            embedding_service=self.embeddings,
            id_column="id",
            content_column="name",
            metadata_columns=["id", "description"],  # Ensure 'id' is in metadata
        )
        self.context_retriever = self.vector_store.as_retriever()
        self.rag_chain = self._create_rag_chain()
        await self._create_form_index_cache()

    async def clear_session_cache(self):
        """Clears all cache entries associated with the current session."""
        logger.info("Clearing cache for session_id: %s", self.session_id)
        try:
            await self.cache.delete(self.FORM_CONTEXT_CACHE_KEY)
            await self.cache.delete(self.HISTORY_CACHE_KEY)
            # Note: This does not clear form responses, which are hashed by form_id.
            # For the test script, this is sufficient as it prevents stale form contexts.
            logger.info("Cache cleared for session_id: %s", self.session_id)
        except Exception as e:
            logger.error("Error clearing cache for session %s: %s", self.session_id, e)

    async def _create_form_index_cache(self):
        """Fetches all forms and caches their essential details."""
        try:
            forms_response = await self.form_repo.find(query=FormQuery(), limit=1000)
            if forms_response and forms_response.data:
                form_index = [
                    {
                        "id": str(form.id),
                        "name": form.name,
                        "description": form.description or "",
                    }
                    for form in forms_response.data
                    if form and form.name
                ]
                if form_index:
                    await self.cache.set(
                        self.FORM_INDEX_CACHE_KEY, form_index, ttl=3600
                    )
                    logger.info(f"Successfully cached {len(form_index)} forms.")
                else:
                    logger.warning("No valid forms found to create index cache.")
        except Exception as e:
            logger.error(f"Failed to create form index cache: {e}")

    async def _initialize_system_prompt(self):
        """Initialize system prompt with caching"""
        if self.system_prompt is not None:
            return

        try:
            cached_prompt = await self.cache.get(self.SYSTEM_PROMPT_CACHE_KEY)
            if cached_prompt:
                self.system_prompt = cached_prompt
                return

            contexts = await self.context_repo.find(query=None)

            if not contexts or not contexts.data:
                self.system_prompt = "You are a helpful assistant."
            else:
                self.system_prompt = self._build_system_prompt(contexts.data)

            await self.cache.set(
                self.SYSTEM_PROMPT_CACHE_KEY, self.system_prompt, ttl=3600
            )

        except Exception as e:
            logger.error(f"Error initializing system prompt: {e}")
            self.system_prompt = "You are a helpful assistant."

    def _build_system_prompt(self, contexts: list) -> str:
        """Build system prompt from contexts"""
        info_contexts = [
            c.data for c in contexts if c.category == ContextCategory.INFORMATION
        ]
        rule_contexts = [c.data for c in contexts if c.category == ContextCategory.RULE]
        param_contexts = [
            c.data for c in contexts if c.category == ContextCategory.PARAMETER
        ]

        prompt_parts = ["You are an AI assistant with the following characteristics:"]

        if param_contexts:
            prompt_parts.append("\n--- PARAMETERS ---")
            prompt_parts.append(
                "You must operate within these parameters at all times:"
            )
            prompt_parts.append(json.dumps(param_contexts, indent=2))

        if rule_contexts:
            prompt_parts.append("\n--- RULES ---")
            prompt_parts.append("You must strictly adhere to the following rules:")
            prompt_parts.append(json.dumps(rule_contexts, indent=2))

        if info_contexts:
            prompt_parts.append("\n--- BACKGROUND INFORMATION ---")
            prompt_parts.append(
                "This is general information you can use to answer questions:"
            )
            prompt_parts.append(json.dumps(info_contexts, indent=2))

        return "\n".join(prompt_parts)

    def _create_rag_chain(self):
        def format_docs(docs: list[Document]) -> str:
            formatted_docs = []
            for doc in docs:
                metadata = doc.metadata
                content = (
                    f"Source Name: {metadata.get('name', 'N/A')}\n"
                    f"Category: {metadata.get('category', 'N/A')}\n"
                    f"Data: {json.dumps(metadata.get('data', {}))}"
                )
                formatted_docs.append(content)
            return "\n\n---\n\n".join(formatted_docs)

        template = """{system_prompt}
                Use the following pieces of retrieved context to answer the user's question.
                If you don't know the answer, just say that you don't know.
                Keep the answer concise and helpful.

                Context:
                {context}

                Question: {question}

                Answer:"""
        prompt = ChatPromptTemplate.from_template(template)

        return (
            {
                "context": self.context_retriever | format_docs,
                "question": RunnablePassthrough(),
                "system_prompt": lambda _: self.system_prompt,
            }
            | prompt
            | self.model
            | StrOutputParser()
        )

    async def _get_conversation_history(self) -> list[BaseMessage]:
        try:
            history_dicts = await self.cache.get(self.HISTORY_CACHE_KEY)
            if history_dicts:
                return messages_from_dict(history_dicts)
        except RedisError as e:
            await self._handle_cache_error("get_conversation_history", e)
        return []

    async def _save_conversation_history(self, history: Sequence[BaseMessage]):
        try:
            history_dicts = messages_to_dict(history)
            await self.cache.set(self.HISTORY_CACHE_KEY, history_dicts)
        except RedisError as e:
            await self._handle_cache_error("save_conversation_history", e)

    async def add_form_context(self, form_id: str):
        """Initialize form context by fetching form data from database"""
        try:
            form_questions = await self._get_form_questions_ordered(form_id)

            if not form_questions:
                logger.error(f"No questions found for form {form_id}")
                raise FormNotFoundError(f"No questions found for form {form_id}")

            form_context = {
                "form_id": form_id,
                "questions": form_questions,
                "current_question_index": 0,
            }

            await self.cache.set(self.FORM_CONTEXT_CACHE_KEY, form_context)

            first_question = form_context["questions"][0]
            return first_question.get("prompt") or first_question.get("label")

        except Exception as e:
            logger.error(f"Error adding form context: {e}")
            return "Sorry, I'm having trouble starting the form. Please try again later."

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

    async def chat(self, user_input: str) -> AsyncGenerator[ChatbotResponse, None]:
        """Handles the chat flow, including form detection and RAG."""
        try:
            # 1. Check if currently in a form-filling flow
            form_context = await self.cache.get(self.FORM_CONTEXT_CACHE_KEY)
            if form_context:
                response_content = await self._handle_form_response(
                    user_input, form_context
                )
                yield {
                    "flow": "form",
                    "content": response_content,
                    "form_id": form_context.get("form_id"),
                }
                return

            # 2. Detect if the user's intent is to start a form
            form_id_str = await self._detect_form_intent(user_input)
            if form_id_str:
                yield {
                    "flow": "form",
                    "content": "I can help with that. To get started, I just need a few details.",
                    "form_id": form_id_str,
                }
                first_question = await self.add_form_context(form_id_str)
                yield {
                    "flow": "form",
                    "content": first_question,
                    "form_id": form_id_str,
                }
                return

            # 3. Fallback to general RAG-based chat
            await self._initialize_system_prompt()
            async for chunk in self._generate_rag_response(user_input):
                yield chunk

        except Exception as e:
            logger.error(f"Error in chat: {e}")
            yield {
                "flow": "generic",
                "content": "Sorry, I'm having trouble responding right now. Please try again later.",
                "form_id": None,
            }

    async def _generate_rag_response(
        self, user_input: str
    ) -> AsyncGenerator[ChatbotResponse, None]:
        try:
            stream_response = self.rag_chain.astream(user_input)
            full_response = ""
            async for chunk in stream_response:
                full_response += chunk
                yield {"flow": "generic", "content": chunk, "form_id": None}

            conversation_history = await self._get_conversation_history()
            conversation_history.append(HumanMessage(content=user_input))
            conversation_history.append(AIMessage(content=full_response))
            await self._save_conversation_history(conversation_history)
        except LangChainException as e:
            logger.error("Error getting chat response/stream: %s", e)
            yield {
                "flow": "generic",
                "content": "Sorry, I'm having trouble responding right now. Please try again later.",
                "form_id": None,
            }

    async def _detect_form_intent(self, user_input: str) -> str | None:
        """Detects if the user's input matches a form's intent."""
        # Guard against very short, generic inputs
        if len(user_input.split()) < 3:
            return None

        # 1. Keyword search on form names (high confidence)
        try:
            form_index = await self.cache.get(self.FORM_INDEX_CACHE_KEY)
            if form_index:
                stop_words = {
                    "a",
                    "an",
                    "the",
                    "is",
                    "in",
                    "it",
                    "of",
                    "for",
                    "i",
                    "want",
                    "to",
                    "get",
                }
                user_input_keywords = set(user_input.lower().split()) - stop_words

                for form in form_index:
                    form_name_keywords = set(form["name"].lower().split())
                    if form_name_keywords & user_input_keywords:
                        logger.info(f"Found keyword match for form '{{form['name']}}'.")
                        return form["id"]
        except Exception as e:
            logger.warning(f"Could not use form index cache for keyword search: {e}")

        # 2. Vector search on form names and descriptions (medium confidence)
        try:
            if not self.form_vector_store:
                raise VectorSearchError("Form vector store is not initialized.")

            results = await self.form_vector_store.asimilarity_search_with_score(
                user_input, k=1
            )

            if results:
                doc, score = results[0]
                max_distance = 0.5  # Stricter threshold
                if score <= max_distance:
                    form_id = str(doc.metadata.get("id"))
                    if form_id and form_id.lower() != "none":
                        logger.info(
                            f"Found semantic match for form '{{doc.page_content}}' with score {score}."
                        )
                        return form_id

        except Exception as e:
            logger.error(f"Error during vector search for form intent: {e}")

        return None

    async def _get_form_questions_ordered(self, form_id: str) -> list[FormQuestion]:
        """Get form questions ordered by section and question order"""
        try:
            form_response = await self.form_repo.get(UUID(form_id))
            if not form_response or not form_response.data:
                logger.error(f"Form with id {form_id} not found via repository.")
                return []

            form = form_response.data

            all_questions = []
            sorted_sections = sorted(form.sections, key=lambda s: s.order)

            for section in sorted_sections:
                sorted_questions = sorted(section.questions, key=lambda q: q.order)
                for q in sorted_questions:
                    all_questions.append(
                        {
                            "id": str(q.id),
                            "label": q.label,
                            "prompt": q.prompt,
                        }
                    )
            return all_questions
        except APIError as e:
            logger.error(f"APIError fetching questions for form {form_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching questions for form {form_id}: {e}")
            return []

    async def _handle_cache_error(self, operation: str, error: Exception):
        """Handle cache-related errors gracefully"""
        logger.error(f"Cache error during {operation}: {error}")

    async def _handle_vector_search_error(self, error: Exception):
        """Handle vector search errors"""
        logger.error(f"Vector search error: {error}")
        raise VectorSearchError("Failed to search for relevant items.") from error