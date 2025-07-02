import re
import subprocess
import sys
from collections.abc import Callable
from typing import Any

import nltk
import spacy
from spacy.language import Language


# --- Download NLTK data ---
def initialize_nltk_data():
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt", quiet=True)
    try:
        nltk.data.find("corpora/stopwords")
    except LookupError:
        nltk.download("stopwords", quiet=True)
    # Adding 'wordnet' for lexical semantics (synonyms, antonyms, etc.)
    try:
        nltk.data.find("corpora/wordnet")
    except LookupError:
        nltk.download("wordnet", quiet=True)
    # Adding 'averaged_perceptron_tagger' for Part-of-Speech tagging
    try:
        nltk.data.find("taggers/averaged_perceptron_tagger")
    except LookupError:
        nltk.download("averaged_perceptron_tagger", quiet=True)


# --- Validation & Extraction Functions ---
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


class SessionCache:
    def __init__(self):
        self.sessions: dict[str, dict[str, Any]] = {}

    def get_context(self, session_id: str) -> dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "conversation_flow": None,
                "lead_captured": False,
                "last_intent": None,
            }
        return self.sessions[session_id]

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]


cache = SessionCache()


class Question:
    def __init__(
        self,
        key: str,
        text: str,
        validation: Callable[[str], bool] | None = None,
        extractor: Callable[[str], Any] | None = None,
        success_message: str | None = None,
    ):
        self.key = key
        self.text = text
        self.validation = validation
        self.extractor = extractor
        self.success_message = success_message


class ConversationFlow:
    def __init__(self, questions: list[Question], completion_message: str):
        self.questions = questions
        self.completion_message = completion_message
        self.current_question_index = 0
        self.is_active = True

    def get_current_question(self) -> Question | None:
        if self.is_active and self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None

    def process_answer(self, answer: str, context: dict[str, Any]) -> str | None:
        question = self.get_current_question()
        if not question:
            self.deactivate()
            return None

        extracted_value = answer
        if question.extractor:
            extracted_value = question.extractor(answer)
            if not extracted_value:
                return f"I didn't quite catch that. {question.text}"

        if question.validation and not question.validation(extracted_value):
            return f"That doesn't right. {question.text}"

        context[question.key] = extracted_value
        if question.success_message:
            print(f"Chatbot: {question.success_message.format(**context)}")

        self.current_question_index += 1
        if self.current_question_index >= len(self.questions):
            self.deactivate()
            context["lead_captured"] = True
            return self.completion_message.format(**context)

        next_question = self.get_current_question()
        return next_question.text if next_question else None

    def deactivate(self):
        self.is_active = False


# --- NLTK Data ---
EXIT_KEYWORDS = ["exit", "cancel", "stop", "nevermind"]

# --- Lead Capture Flow Definition ---
LEAD_CAPTURE_FLOW_TEMPLATE = ConversationFlow(
    questions=[
        Question(
            "info_name",
            "What is your full name?",
            extractor=None,  # This will be set in nlp_utils
            success_message="Thanks, {info_name}!",
        ),
        Question(
            "info_email",
            "What is your email address?",
            validation=None,  # This will be set in nlp_utils
        ),
    ],
    completion_message="Perfect! Thank you, {info_name}. I have your email ({info_email}). Our sales team will be in touch.",
)
