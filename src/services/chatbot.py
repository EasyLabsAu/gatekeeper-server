import json
import pickle
import random
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import aiofiles
import nltk
import numpy as np
import spacy
from annoy import AnnoyIndex
from spacy.language import Language

from src.helpers.cache import Cache, PickleSerializer
from src.helpers.logger import Logger
from src.helpers.model import utc_now
from src.models.forms import (
    FormFieldTypes,
    FormRead,
)

logger = Logger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
INTENTS_FILE = DATA_DIR / "intents.json"
EMBEDDINGS_FILE = DATA_DIR / "intents_embeddings.pkl"
ANNOY_INDEX_FILE = DATA_DIR / "intents_annoy_index.ann"


def initialize_nltk_data():
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt", quiet=True)
    try:
        nltk.data.find("corpora/stopwords")
    except LookupError:
        nltk.download("stopwords", quiet=True)
    try:
        nltk.data.find("corpora/wordnet")
    except LookupError:
        nltk.download("wordnet", quiet=True)
    try:
        nltk.data.find("taggers/averaged_perceptron_tagger")
    except LookupError:
        nltk.download("averaged_perceptron_tagger", quiet=True)


def is_valid_name(name: str) -> bool:
    return len(name.split()) >= 2


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))


def extract_name(text: str, nlp_model: Language) -> str:
    doc = nlp_model(text)
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text
    if len(text.split()) >= 2:
        return text
    return ""


def extract_email(text: str) -> str:
    match = re.search(r"[^@]+@[^@]+\.[^@]+", text)
    return match.group(0) if match else ""


def extract_entities(text: str, nlp_model: Language) -> list[tuple[str, str]]:
    doc = nlp_model(text)
    return [(ent.text, ent.label_) for ent in doc.ents]


def load_spacy_model(model_name: str) -> Language | None:
    try:
        nlp_model = spacy.load(model_name)
        logger.info("spaCy model loaded successfully.")
    except OSError:
        logger.info("spaCy model '%s' not found. Attempting to download...", model_name)
        try:
            subprocess.check_call(
                [sys.executable, "-m", "spacy", "download", model_name]
            )
            nlp_model = spacy.load(model_name)
            logger.info("spaCy model downloaded and loaded successfully.")
        except (subprocess.CalledProcessError, OSError) as e:
            logger.error("Failed to download or load spaCy model: %s", e)
            nlp_model = None
    return nlp_model


EXIT_KEYWORDS = ["exit", "cancel", "stop", "nevermind", "bye"]


async def precompute_embeddings(nlp_model: Language):
    logger.info("Loading intents from %s...", INTENTS_FILE)

    async with aiofiles.open(INTENTS_FILE, encoding="utf-8") as f:
        content = await f.read()
        intents_data = json.loads(content)

    patterns = []
    intent_labels = []
    for intent_name, data in intents_data.items():
        for pattern in data["patterns"]:
            patterns.append(pattern)
            intent_labels.append(intent_name)

    if not patterns:
        logger.info(
            "No patterns found in intents.json. Skipping embedding pre-computation."
        )
        return

    logger.info("Generating embeddings for %d patterns...", len(patterns))
    pattern_embeddings = [nlp_model(text).vector for text in patterns]

    if not pattern_embeddings:
        logger.info("No valid embeddings generated. Skipping Annoy index build.")
        return

    embedding_dim = len(pattern_embeddings[0])
    annoy_index = AnnoyIndex(embedding_dim, "angular")
    for i, vec in enumerate(pattern_embeddings):
        annoy_index.add_item(i, vec)

    logger.info("Building Annoy index...")
    annoy_index.build(10)

    annoy_index.save(str(ANNOY_INDEX_FILE))
    logger.info("Annoy index saved to %s", ANNOY_INDEX_FILE)

    intent_mapping = {i: (intent_labels[i], patterns[i]) for i in range(len(patterns))}

    async with aiofiles.open(EMBEDDINGS_FILE, mode="wb") as f:
        await f.write(pickle.dumps(intent_mapping))

    logger.info("Intent mapping saved to %s", EMBEDDINGS_FILE)
    logger.info("Pre-computation complete.")


class Question:
    def __init__(
        self,
        text: str,
        field_type: str | None,
        required: bool | None,
        options: list[str] | None,
        question_id: UUID | None,
        section_id: UUID | None,
        key: str | None = None,
        validation: Callable[[str], bool] | None = None,
        extractor: Callable[[str], Any] | None = None,
        success_message: str | None = None,
    ):
        self.text = text
        self.field_type = field_type
        self.required = required
        self.options = options
        self.question_id = question_id
        self.section_id = section_id
        self.key = key
        self.validation = validation
        self.extractor = extractor
        self.success_message = success_message


class Chatbot:
    def __init__(
        self,
        session_id: str,
        model_name="en_core_web_lg",
        min_overall_confidence=0.7,
    ):
        self.session_id = session_id
        self.min_overall_confidence = min_overall_confidence
        self.context: dict[str, Any] = {}

        self.cache = Cache(
            key_prefix="chatbot_context",
            serializer=PickleSerializer(),
            default_ttl=86400,
        )

        try:
            self.nlp = spacy.load(model_name)
        except OSError as exc:
            raise RuntimeError(
                f"SpaCy model '{model_name}' not found. Please ensure it's downloaded."
            ) from exc

        if self.nlp.vocab.vectors.shape[0] > 0:
            self.embedding_dim = self.nlp.vocab.vectors.shape[1]
        else:
            self.embedding_dim = 300
            logger.warning(
                "Warning: SpaCy model '%s' has no loaded vectors. Using default embedding_dim=%d",
                model_name,
                self.embedding_dim,
            )

        self.intents_data = {}
        self.annoy_index = None
        self.intent_mapping = {}
        self._assets_loaded = False

    async def _load_intent_assets(self):
        if self._assets_loaded:
            return

        if not ANNOY_INDEX_FILE.exists() or not EMBEDDINGS_FILE.exists():
            logger.info(
                "Pre-computed embeddings or Annoy index not found. Running pre-computation..."
            )
            initialize_nltk_data()
            await precompute_embeddings(self.nlp)

        try:
            self.annoy_index = AnnoyIndex(self.embedding_dim, "angular")
            self.annoy_index.load(str(ANNOY_INDEX_FILE))
        except OSError as e:
            logger.error("Failed to load Annoy index: %s", e)
            return

        try:
            async with aiofiles.open(EMBEDDINGS_FILE, mode="rb") as f:
                data = await f.read()
                self.intent_mapping = pickle.loads(data)
        except (pickle.UnpicklingError, OSError) as e:
            logger.error("Failed to load intent embeddings: %s", e)
            self.annoy_index = None
            return

        try:
            async with aiofiles.open(INTENTS_FILE, encoding="utf-8") as f:
                content = await f.read()
                self.intents_data = json.loads(content)
        except (ValueError, TypeError, KeyError) as e:
            logger.error("Failed to load intents data: %s", e)
            self.annoy_index = None
            self.intent_mapping = {}
            return

        self._assets_loaded = True

    async def load_context(self):
        context = await self.cache.get(self.session_id)
        self.context = context if isinstance(context, dict) else {}

    async def save_context(self):
        await self.cache.set(self.session_id, self.context)

    @property
    def last_intent(self) -> str | None:
        return self.context.get("last_intent")

    @last_intent.setter
    def last_intent(self, intent: str | None):
        self.context["last_intent"] = intent

    def _recognize_intent(self, text: str, top_n=5) -> tuple[str, float, list]:
        if not text.strip():
            return "invalid", 0.0, []

        if not self.annoy_index:
            logger.warning("Annoy index not loaded. Cannot recognize intent.")
            return "invalid", 0.0, []

        text_embedding = self.nlp(text).vector
        indices, _ = self.annoy_index.get_nns_by_vector(
            text_embedding, top_n, include_distances=True
        )

        best_intent = "invalid"
        best_score = 0.0
        matched_patterns = []

        for idx in indices:
            intent_label, original_pattern = self.intent_mapping[idx]
            original_pattern_embedding = self.nlp(original_pattern).vector

            text_embedding_np = np.asarray(text_embedding)
            original_pattern_embedding_np = np.asarray(original_pattern_embedding)

            norm_text = np.linalg.norm(text_embedding_np)
            norm_pattern = np.linalg.norm(original_pattern_embedding_np)

            score = (
                np.dot(text_embedding_np, original_pattern_embedding_np)
                / (norm_text * norm_pattern)
                if norm_text > 0 and norm_pattern > 0
                else 0.0
            )

            if score > best_score:
                best_score = score
                best_intent = intent_label

            if score >= self.min_overall_confidence:
                matched_patterns.append(
                    {
                        "intent": intent_label,
                        "pattern": original_pattern,
                        "score": score,
                    }
                )

        if best_score < self.min_overall_confidence:
            return "invalid", 0.0, []

        return best_intent, best_score, matched_patterns

    def _get_responses(self, intent_name: str) -> list[str]:
        if intent_name not in self.intents_data:
            return ["I'm sorry, I don't have a response for that."]
        responses = self.intents_data[intent_name]["responses"]
        return (
            responses
            if isinstance(responses, list)
            else ["I'm sorry, I need more information."]
        )

    def _is_flow_active(self) -> bool:
        flow = self.context.get("conversation_flow")
        return bool(flow and flow.get("is_active", False))

    def _deactivate_flow(self):
        if "conversation_flow" in self.context:
            self.context["conversation_flow"]["is_active"] = False

    def _get_current_question(self) -> Question | None:
        if not self._is_flow_active():
            return None
        flow = self.context["conversation_flow"]
        questions = flow.get("questions", [])
        index = flow.get("current_question_index", 0)
        if 0 <= index < len(questions):
            q_data = questions[index]
            q_data["question_id"] = (
                UUID(q_data["question_id"])
                if isinstance(q_data["question_id"], str)
                else q_data["question_id"]
            )
            q_data["section_id"] = (
                UUID(q_data["section_id"])
                if isinstance(q_data["section_id"], str)
                else q_data["section_id"]
            )
            return Question(**q_data)
        return None

    async def _start_form_conversation(self, form: dict | None) -> str | None:
        if not form:
            return "I couldn't find that form."

        questions_data = [
            question
            for section in sorted(
                form.get("sections", []),
                key=lambda s: s.get("order", 0),
            )
            for question in sorted(
                section.get("questions", []),
                key=lambda q: q.get("order", 0),
            )
        ]

        if not questions_data:
            return "This form has no questions defined."

        conversation_questions = [
            {
                "text": q.get("prompt") or q.get("label"),
                "field_type": q.get("field_type"),
                "required": q.get("required"),
                "options": q.get("options"),
                "question_id": str(q.get("id")),
                "section_id": str(q.get("section_id")),
            }
            for q in questions_data
        ]

        completion_message = f"Thank you for completing the '{form.get('name')}' form!"

        self.context["conversation_flow"] = {
            "questions": conversation_questions,
            "completion_message": completion_message,
            "current_question_index": 0,
            "is_active": True,
            "current_question_invalid_attempts": 0,
        }
        self.context["form_id"] = str(form.get("id"))
        self.context["form_responses"] = []

        current_question = self._get_current_question()
        return current_question.text if current_question else completion_message

    async def _process_form_answer(self, user_input: str) -> str:
        current_question = self._get_current_question()
        if not current_question:
            self._deactivate_flow()
            return "It seems there was an issue with the form. Let's start over."

        validation_error = self._validate_answer(user_input, current_question)
        if validation_error:
            self.context["conversation_flow"]["current_question_invalid_attempts"] += 1
            if (
                self.context["conversation_flow"]["current_question_invalid_attempts"]
                >= 3
            ):
                self._deactivate_flow()
                self.context["conversation_flow"][
                    "current_question_invalid_attempts"
                ] = 0
                return "It seems you're having trouble. Let's try something else. What would you like to do?"

            if (
                self.context["conversation_flow"]["current_question_invalid_attempts"]
                == 1
            ):
                return current_question.text
            else:
                return f"{validation_error}\n{current_question.text}"
        else:
            self.context["conversation_flow"]["current_question_invalid_attempts"] = 0
            await self._save_form_response(user_input, current_question)
            flow = self.context["conversation_flow"]

            if flow["current_question_index"] >= len(flow["questions"]) - 1:
                completion_message = flow["completion_message"]
                self._deactivate_flow()
                self.context.pop("form_id", None)
                await self._finalize_form_submission()
                return completion_message
            else:
                flow["current_question_index"] += 1
                next_question = self._get_current_question()
                return next_question.text if next_question else "Something went wrong."

    async def _save_form_response(self, answer: str, question: Question):
        if question.field_type == FormFieldTypes.DATETIME.value:
            try:
                # Try YYYY-MM-DD format first
                parsed_answer = datetime.strptime(answer, "%Y-%m-%d")
            except ValueError:
                # Fallback to ISO format if YYYY-MM-DD fails
                parsed_answer = datetime.fromisoformat(answer)
            processed_answer = parsed_answer.isoformat()
        else:
            processed_answer = answer

        form_responses = self.context.get("form_responses", [])
        question_id_str = str(question.question_id)
        form_id = self.context.get("form_id")

        found = False
        for response in form_responses:
            if response.get("question_id") == question_id_str:
                response["answer"] = processed_answer
                found = True
                break

        if not found:
            form_responses.append(
                {
                    "question_id": question_id_str,
                    "question": question.text,
                    "answer": processed_answer,
                    "form_id": form_id,
                }
            )

        self.context["form_responses"] = form_responses
        logger.info(f" Question: {question.text}")
        logger.info(f"  Answer: {processed_answer}")

    async def _finalize_form_submission(self):
        form_responses = self.context.get("form_responses")
        if form_responses:
            logger.info(f"  Form Responses: {json.dumps(form_responses, indent=2)}")
            logger.info(f"  Submitted At: {datetime.now().isoformat()}")

        self.context["form_id"] = None
        if "form_responses" in self.context:
            del self.context["form_responses"]

    def _validate_answer(self, answer: str, question: Question) -> str | None:
        if question.required and not answer.strip():
            return "This question is required."
        if not answer.strip():
            return None

        field_type = question.field_type
        if field_type == FormFieldTypes.NUMBER.value:
            try:
                float(answer)
            except ValueError:
                return "Please enter a valid number."
        elif field_type == FormFieldTypes.BOOLEAN.value:
            if answer.lower() not in ["true", "false", "yes", "no"]:
                return "Please answer with 'true' or 'false' (or 'yes'/'no')."
        elif field_type in [
            FormFieldTypes.SINGLE_CHOICE.value,
            FormFieldTypes.MULTIPLE_CHOICE.value,
        ]:
            options = [opt.lower() for opt in (question.options or [])]
            if field_type == FormFieldTypes.SINGLE_CHOICE.value:
                if answer.lower() not in options:
                    return f"Please choose one of the following options: {', '.join(question.options or [])}"
            else:
                chosen_options = [opt.strip().lower() for opt in answer.split(",")]
                if any(opt not in options for opt in chosen_options):
                    return f"One or more of your choices are not valid. Please choose from: {', '.join(question.options or [])}"
        elif field_type == FormFieldTypes.DATETIME.value:
            try:
                datetime.strptime(answer, "%Y-%m-%d")
            except ValueError:
                try:
                    datetime.fromisoformat(answer)
                except ValueError:
                    return "Please enter a valid date in YYYY-MM-DD format."
        return None

    async def get_response(
        self, user_input: str, form: FormRead | None = None
    ) -> dict[str, str | None | dict]:
        await self.load_context()
        await self._load_intent_assets()
        logger.info("User input: %s", user_input)
        response = "Hey there! How can I help you?"
        sender = "bot"
        timestamp = utc_now().isoformat()
        meta_data = None

        if self.context.get("form_responses"):
            meta_data = {
                "form_responses": self.context.get("form_responses"),
            }

        try:
            if not isinstance(user_input, str) or not user_input.strip():
                return {
                    "sender": sender,
                    "timestamp": timestamp,
                    "form": self.context.get("form_id"),
                    "message": random.choice(self._get_responses("invalid")),
                    "meta_data": meta_data,
                }

            if any(keyword in user_input.lower() for keyword in EXIT_KEYWORDS):
                if self._is_flow_active():
                    self._deactivate_flow()
                    self.context.pop("form_id", None)
                    self.last_intent = "invalid"
                    response = "Okay, cancelling that. What would you like to do?"
                    return {
                        "sender": sender,
                        "timestamp": timestamp,
                        "form": self.context.get("form_id"),
                        "message": response,
                        "meta_data": meta_data,
                    }

            if self._is_flow_active() and self.context.get("form_id"):
                response = await self._process_form_answer(user_input)
                return {
                    "sender": sender,
                    "timestamp": timestamp,
                    "form": self.context.get("form_id"),
                    "message": response,
                    "meta_data": meta_data,
                }

            if self._is_flow_active() and not self.context.get("form_id"):
                self._deactivate_flow()

            if form:
                data = form.model_dump() if isinstance(form, FormRead) else form
                response = await self._start_form_conversation(data)
                self.last_intent = "form_started"
                if not response:
                    response = "Something went wrong starting the form."
                return {
                    "sender": sender,
                    "timestamp": timestamp,
                    "form": self.context.get("form_id"),
                    "message": response,
                    "meta_data": meta_data,
                }

            intent, _, _ = self._recognize_intent(user_input.lower())
            logger.info("Final intent recognized: %s", intent)
            self.last_intent = intent

            if intent == "help":
                capabilities = [
                    key.replace("_", " ")
                    for key, data in self.intents_data.items()
                    if key not in ["invalid", "affirmative", "help"]
                    and data.get("patterns")
                ]
                response = (
                    f"I can help you with: {', '.join(capabilities)}. What would you like assistance with?"
                    if capabilities
                    else "I'm a simple chatbot right now, but I can help with simple questions."
                )
            elif intent and intent != "invalid":
                response = random.choice(self._get_responses(intent))
            else:
                response = random.choice(self._get_responses("invalid"))

            return {
                "sender": sender,
                "timestamp": timestamp,
                "form": self.context.get("form_id"),
                "message": response,
                "meta_data": meta_data,
            }

        finally:
            await self.save_context()
