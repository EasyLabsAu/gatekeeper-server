import json
import os
from collections.abc import AsyncGenerator, Sequence
from typing import Any, TypedDict

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
from src.models.contexts import ContextCategory, Contexts
from src.models.forms import FormQuestions, Forms, FormSections
from src.repositories.contexts import ContextRepository

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
        self.vector_store: AsyncPGVectorStore | None = None
        self.form_vector_store: AsyncPGVectorStore | None = None
        self.form_section_vector_store: AsyncPGVectorStore | None = None
        self.form_question_vector_store: AsyncPGVectorStore | None = None
        self.context_retriever: Any = None
        self.form_retriever: Any = None
        self.form_section_retriever: Any = None
        self.form_question_retriever: Any = None
        self.context_repo = ContextRepository()
        self.system_prompt: str | None = None
        self.rag_chain: Any = None

    async def initialize(self):
        engine = PGEngine.from_connection_string(url=str(settings.POSTGRES_URI))
        self.vector_store = await AsyncPGVectorStore.create(
            engine=engine,
            table_name=str(Contexts.__tablename__),
            embedding_service=self.embeddings,
            id_column="id",
            content_column="data",
        )
        self.form_vector_store = await AsyncPGVectorStore.create(
            engine=engine,
            table_name=str(Forms.__tablename__),
            embedding_service=self.embeddings,
            id_column="id",
            content_column="name",
            metadata_columns=["description"],
        )
        self.form_section_vector_store = await AsyncPGVectorStore.create(
            engine=engine,
            table_name=str(FormSections.__tablename__),
            embedding_service=self.embeddings,
            id_column="id",
            content_column="title",
            metadata_columns=["description"],
        )
        self.form_question_vector_store = await AsyncPGVectorStore.create(
            engine=engine,
            table_name=str(FormQuestions.__tablename__),
            embedding_service=self.embeddings,
            id_column="id",
            content_column="label",
            metadata_columns=["prompt", "options"],
        )
        self.context_retriever = self.vector_store.as_retriever()
        self.form_retriever = self.form_vector_store.as_retriever()
        self.form_section_retriever = self.form_section_vector_store.as_retriever()
        self.form_question_retriever = self.form_question_vector_store.as_retriever()
        self.rag_chain = self._create_rag_chain()

    async def _initialize_system_prompt(self):
        if self.system_prompt is not None:
            return

        contexts = await self.context_repo.find(query=None)
        if not contexts or not contexts.data:
            self.system_prompt = "You are a helpful assistant."
            return

        info_contexts = [
            c.data for c in contexts.data if c.category == ContextCategory.INFORMATION
        ]
        rule_contexts = [
            c.data for c in contexts.data if c.category == ContextCategory.RULE
        ]
        param_contexts = [
            c.data for c in contexts.data if c.category == ContextCategory.PARAMETER
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

        self.system_prompt = "\n".join(prompt_parts)

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

    async def chat(self, user_input: str) -> AsyncGenerator[ChatbotResponse, None]:
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

        await self._initialize_system_prompt()

        if (
            self.form_vector_store
            and self.form_section_vector_store
            and self.form_question_vector_store
        ):
            try:
                relevant_forms_docs = await self.form_retriever.aget_relevant_documents(
                    user_input
                )
                relevant_sections_docs = (
                    await self.form_section_retriever.aget_relevant_documents(
                        user_input
                    )
                )
                relevant_questions_docs = (
                    await self.form_question_retriever.aget_relevant_documents(
                        user_input
                    )
                )

                combined_relevant_items = []
                for doc in relevant_forms_docs:
                    combined_relevant_items.append(
                        {
                            "type": "form",
                            "id": str(doc.metadata.get("id")),
                            "name": doc.page_content,
                            "description": doc.metadata.get("description"),
                        }
                    )
                for doc in relevant_sections_docs:
                    combined_relevant_items.append(
                        {
                            "type": "section",
                            "id": str(doc.metadata.get("id")),
                            "title": doc.page_content,
                            "description": doc.metadata.get("description"),
                        }
                    )
                for doc in relevant_questions_docs:
                    combined_relevant_items.append(
                        {
                            "type": "question",
                            "id": str(doc.metadata.get("id")),
                            "label": doc.page_content,
                            "prompt": doc.metadata.get("prompt"),
                            "options": doc.metadata.get("options"),
                        }
                    )

                if combined_relevant_items:
                    prompt = f"""Given the user's message, your goal is to determine if they are expressing an intent to start or fill out a form, or if they are asking a question about a specific form, section, or question.

                    User message: {user_input}

                    Available relevant items (ranked by relevance, most relevant first):
                    {json.dumps(combined_relevant_items, indent=2)}

                    Instructions:
                    1. Analyze the user's message and the provided relevant items.
                    2. If the user's message clearly indicates a desire to start or fill out a form, identify the most relevant form from the 'combined_relevant_items' and return a JSON object with the key 'form_id' and the ID of that form. Prioritize forms if the intent is clear.
                    3. If the user is asking a question about a specific form, section, or question (e.g., \"What is the 'Paint Job Request' form about?\", \"Tell me about the 'Customer Info' section\", \"What is the 'Name' question?\"), identify the most relevant item and return a JSON object with the key 'item_type' (e.g., 'form', 'section', or 'question') and 'item_id'.
                    4. If no clear intent to start a form or inquire about a specific item is found, return an empty JSON object {{}}.

                    Examples of user intent and expected JSON output:
                    - User wants to start a form: \"I want to request a paint job\" -> {{\"form_id\": \"id_of_paint_job_form\"}}
                    - User asks about a form: \"What is the paint job form?\" -> {{\"item_type\": \"form\", \"item_id\": \"id_of_paint_job_form\"}}
                    - User asks about a section: \"Tell me about the customer info section\" -> {{\"item_type\": \"section\", \"item_id\": \"id_of_customer_info_section\"}}
                    - User asks about a question: \"What is the name question?\" -> {{\"item_type\": \"question\", \"item_id\": \"id_of_name_question\"}}
                    - User asks a general question not related to forms: \"What is your company?\" -> {{}}

                    Your JSON response:"""
                    response = await self.model.ainvoke([HumanMessage(content=prompt)])
                    if isinstance(response.content, str):
                        cleaned_response = response.content.strip()
                        if cleaned_response.startswith(
                            "{"
                        ) and cleaned_response.endswith("}"):
                            response_json = json.loads(cleaned_response)
                            if "form_id" in response_json and response_json["form_id"]:
                                yield {
                                    "type": "form_start",
                                    "content": "",
                                    "form_id": response_json["form_id"],
                                }
                                return
                            elif (
                                "item_type" in response_json
                                and "item_id" in response_json
                            ):
                                yield {
                                    "type": "info",
                                    "content": f"You asked about a {response_json['item_type']} with ID: {response_json['item_id']}. I can provide more details if needed.",
                                    "form_id": None,
                                }
                                return
            except (LangChainException, json.JSONDecodeError) as e:
                logger.warning(
                    "Could not identify form, section, or question using vector search, proceeding with RAG: %s",
                    e,
                )

        try:
            stream_response = self.rag_chain.astream(user_input)
            full_response = ""
            async for chunk in stream_response:
                full_response += chunk
                yield {"type": "chat", "content": chunk, "form_id": None}

            conversation_history = await self._get_conversation_history()
            conversation_history.append(HumanMessage(content=user_input))
            conversation_history.append(AIMessage(content=full_response))
            await self._save_conversation_history(conversation_history)
        except LangChainException as e:
            logger.error("Error getting chat response/stream: %s", e)
            yield {
                "type": "chat",
                "content": "Sorry, I'm having trouble responding right now. Please try again later.",
                "form_id": None,
            }
