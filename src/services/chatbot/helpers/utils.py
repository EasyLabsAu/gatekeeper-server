import re
import subprocess
import sys

import nltk
import spacy
from spacy.language import Language

from src.services.chatbot.helpers.flows import ConversationFlow, Question


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


# --- NLTK Data ---
EXIT_KEYWORDS = ["exit", "cancel", "stop", "nevermind"]

# --- Lead Capture Flow Definition ---
LEAD_CAPTURE_FLOW_TEMPLATE = ConversationFlow(
    questions=[
        Question(
            question_id=None,
            section_id=None,
            text="What is your full name?",
            field_type="text",
            required=True,
            options=None,
            key="info_name",
            extractor=None,  # This will be set in core
            success_message="Thanks, {info_name}!",
        ),
        Question(
            question_id=None,
            section_id=None,
            text="What is your email address?",
            field_type="text",
            required=True,
            options=None,
            key="info_email",
            validation=None,  # This will be set in core
        ),
    ],
    completion_message="Perfect! Thank you, {info_name}. I have your email ({info_email}). Our sales team will be in touch.",
)
