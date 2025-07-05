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

import nltk
import numpy as np
import spacy
from annoy import AnnoyIndex
from spacy.language import Language

from src.helpers.cache import Cache, PickleSerializer
from src.models.forms import (
    FormFieldTypes,
)

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
    # Fallback for simple names
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
        print("spaCy model loaded successfully.")
    except OSError:
        print(f"spaCy model '{model_name}' not found. Attempting to download...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "spacy", "download", model_name]
            )
            nlp_model = spacy.load(model_name)
            print("spaCy model downloaded and loaded successfully.")
        except (subprocess.CalledProcessError, OSError) as e:
            print(f"Failed to download or load spaCy model: {e}")
            nlp_model = None
    return nlp_model


EXIT_KEYWORDS = ["exit", "cancel", "stop", "nevermind", "bye"]


def precompute_embeddings(nlp_model: Language):
    print(f"Loading intents from {INTENTS_FILE}...")
    with open(INTENTS_FILE, encoding="utf-8") as f:
        intents_data = json.load(f)

    patterns = []
    intent_labels = []
    for intent_name, data in intents_data.items():
        for pattern in data["patterns"]:
            patterns.append(pattern)
            intent_labels.append(intent_name)

    if not patterns:
        print("No patterns found in intents.json. Skipping embedding pre-computation.")
        return

    print(f"Generating embeddings for {len(patterns)} patterns...")
    pattern_embeddings = [nlp_model(text).vector for text in patterns]

    if not pattern_embeddings:
        print("No valid embeddings generated. Skipping Annoy index build.")
        return

    embedding_dim = len(pattern_embeddings[0])

    annoy_index = AnnoyIndex(
        embedding_dim, "angular"
    )  # angular distance is cosine similarity
    for i, vec in enumerate(pattern_embeddings):
        annoy_index.add_item(i, vec)

    print("Building Annoy index...")
    annoy_index.build(10)  # 10 trees for good balance between speed and accuracy

    annoy_index.save(str(ANNOY_INDEX_FILE))
    print(f"Annoy index saved to {ANNOY_INDEX_FILE}")

    intent_mapping = {i: (intent_labels[i], patterns[i]) for i in range(len(patterns))}
    with open(EMBEDDINGS_FILE, "wb") as f:
        pickle.dump(intent_mapping, f)
    print(f"Intent mapping saved to {EMBEDDINGS_FILE}")

    print("Pre-computation complete.")


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
            print(
                f"Warning: SpaCy model '{model_name}' has no loaded vectors. Using default embedding_dim={self.embedding_dim}"
            )

        self._load_intent_assets()

    def _load_intent_assets(self):
        if not ANNOY_INDEX_FILE.exists() or not EMBEDDINGS_FILE.exists():
            print(
                "Pre-computed embeddings or Annoy index not found. Running pre-computation..."
            )
            initialize_nltk_data()
            precompute_embeddings(self.nlp)

        self.annoy_index = AnnoyIndex(self.embedding_dim, "angular")
        self.annoy_index.load(str(ANNOY_INDEX_FILE))

        with open(EMBEDDINGS_FILE, "rb") as f:
            self.intent_mapping = pickle.load(f)

        with open(INTENTS_FILE, encoding="utf-8") as f:
            self.intents_data = json.load(f)

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
            # Ensure question_id and section_id are UUIDs
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

    async def _start_form_conversation(self, form: dict) -> str | None:
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
        }
        self.context["current_form_id"] = str(form.get("id"))
        self.context["form_responses_id"] = None

        current_question = self._get_current_question()
        return current_question.text if current_question else completion_message

    async def _process_form_answer(self, user_input: str) -> str:
        current_question = self._get_current_question()
        if not current_question:
            self._deactivate_flow()
            return "It seems there was an issue with the form. Let's start over."

        validation_error = self._validate_answer(user_input, current_question)
        if validation_error:
            self.context["invalid_answer_count"] = (
                self.context.get("invalid_answer_count", 0) + 1
            )
            if self.context["invalid_answer_count"] >= 3:
                self._deactivate_flow()
                self.context["invalid_answer_count"] = 0
                return "It seems you're having trouble. Let's try something else. What would you like to do?"
            return f"{validation_error}. {current_question.text}"

        self.context["invalid_answer_count"] = 0
        await self._save_form_response(user_input, current_question)

        flow = self.context["conversation_flow"]
        flow["current_question_index"] += 1

        if flow["current_question_index"] >= len(flow["questions"]):
            self._deactivate_flow()
            await self._finalize_form_submission()
            return flow["completion_message"]

        next_question = self._get_current_question()
        return next_question.text if next_question else "Something went wrong."

    async def _save_form_response(self, answer: str, question: Question):
        form_responses_id_str = self.context.get("form_responses_id")
        current_form_id_str = self.context.get("current_form_id")

        if not form_responses_id_str:
            new_form_response_id = str(UUID(int=random.randint(0, 2**32 - 1)))
            self.context["form_responses_id"] = new_form_response_id
            form_responses_id = new_form_response_id
            print("--- New Form Response ---")
            print(f"  Form Response ID: {form_responses_id}")
            print(f"  Form ID: {current_form_id_str}")
            print(f"  Session ID: {self.session_id}")
        else:
            form_responses_id = form_responses_id_str

        if "section_responses" not in self.context:
            self.context["section_responses"] = {}

        section_id_str = str(question.section_id)
        if section_id_str not in self.context["section_responses"]:
            new_section_response_id = str(UUID(int=random.randint(0, 2**32 - 1)))
            self.context["section_responses"][section_id_str] = new_section_response_id
            print("--- New Section Response ---")
            print(f"  Section Response ID: {new_section_response_id}")
            print(f"  Form Response ID: {form_responses_id}")
            print(f"  Section ID: {section_id_str}")

        section_response_id = self.context["section_responses"][section_id_str]

        question_response = {
            "section_response_id": section_response_id,
            "question_id": str(question.question_id),
            "answer": answer,
            "submitted_at": datetime.now().isoformat(),
        }
        print("--- New Question Response ---")
        print(json.dumps(question_response, indent=2))

    async def _finalize_form_submission(self):
        form_responses_id_str = self.context.get("form_responses_id")
        if form_responses_id_str:
            print("--- Form Submission Finalized ---")
            print(f"  Form Response ID: {form_responses_id_str}")
            print(f"  Submitted At: {datetime.now().isoformat()}")

        self.context["current_form_id"] = None
        self.context["form_responses_id"] = None
        if "section_responses" in self.context:
            del self.context["section_responses"]

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
            options = question.options or []
            if field_type == FormFieldTypes.SINGLE_CHOICE.value:
                if answer not in options:
                    return f"Please choose one of the following options: {', '.join(options)}"
            else:  # MULTIPLE_CHOICE
                chosen_options = [opt.strip() for opt in answer.split(",")]
                if any(opt not in options for opt in chosen_options):
                    return f"One or more of your choices are not valid. Please choose from: {', '.join(options)}"
        elif field_type == FormFieldTypes.DATETIME.value:
            try:
                datetime.fromisoformat(answer)
            except ValueError:
                return "Please enter a valid date and time in ISO format (YYYY-MM-DDTHH:MM:SS)."
        return None

    async def get_response(self, user_input: str, form: dict | None = None) -> str:
        await self.load_context()
        response = ""
        try:
            if not isinstance(user_input, str) or not user_input.strip():
                return random.choice(self._get_responses("invalid"))

            if any(keyword in user_input.lower() for keyword in EXIT_KEYWORDS):
                if self._is_flow_active():
                    self._deactivate_flow()
                    self.last_intent = "invalid"
                    return "Okay, cancelling that. What would you like to do?"

            if self._is_flow_active():
                if self.context.get("current_form_id"):
                    response = await self._process_form_answer(user_input)
                else:
                    self._deactivate_flow()
                    response = "Flow interrupted. What would you like to do?"
                return response

            if form:
                response = await self._start_form_conversation(form)
                self.last_intent = "form_started"
                return response or "Something went wrong starting the form."

            intent, _, _ = self._recognize_intent(user_input)
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

            return response

        finally:
            await self.save_context()
