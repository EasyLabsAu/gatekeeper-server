import json
import pickle
import random
from pathlib import Path

import numpy as np
import spacy
from annoy import AnnoyIndex

from src.services.chatbot.helpers import (
    EXIT_KEYWORDS,
    LEAD_CAPTURE_FLOW_TEMPLATE,
    ConversationFlow,
    cache,
    extract_entities,
    extract_name,
    is_valid_email,
)


class IntentRecognizer:
    def __init__(self, model_name="en_core_web_lg", num_trees=10):
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

        self.num_trees = num_trees

        self.intents_file = Path(__file__).parent / "data" / "intents.json"
        self.embeddings_file = Path(__file__).parent / "data" / "intents_embeddings.pkl"
        self.annoy_index_file = (
            Path(__file__).parent / "data" / "intents_annoy_index.ann"
        )

        self._load_assets()

    def _load_assets(self):
        if not self.annoy_index_file.exists() or not self.embeddings_file.exists():
            raise FileNotFoundError(
                "Pre-computed embeddings or Annoy index not found. Please run precompute_embeddings.py first."
            )

        self.annoy_index = AnnoyIndex(self.embedding_dim, "angular")
        self.annoy_index.load(str(self.annoy_index_file))

        with open(self.embeddings_file, "rb") as f:
            self.intent_mapping = pickle.load(f)

        with open(self.intents_file, encoding="utf-8") as f:
            self.intents_data = json.load(f)

    def recognize_intent(self, text, top_n=5, threshold=0.7):
        if not text.strip():
            return "invalid", 0.0, []

        text_embedding = self.nlp(text).vector

        indices, distances = self.annoy_index.get_nns_by_vector(
            text_embedding, top_n, include_distances=True
        )

        best_intent = "invalid"
        best_score = 0.0
        matched_patterns = []

        for _, idx in enumerate(indices):
            intent_label, original_pattern = self.intent_mapping[idx]
            original_pattern_embedding = self.nlp(original_pattern).vector

            # Explicitly cast to numpy array to satisfy type checker
            text_embedding_np = np.asarray(text_embedding)
            original_pattern_embedding_np = np.asarray(original_pattern_embedding)

            norm_text = np.linalg.norm(text_embedding_np)
            norm_pattern = np.linalg.norm(original_pattern_embedding_np)

            if norm_text == 0 or norm_pattern == 0:
                score = 0.0
            else:
                score = np.dot(text_embedding_np, original_pattern_embedding_np) / (
                    norm_text * norm_pattern
                )

            if score > best_score:
                best_score = score
                best_intent = intent_label

            if score >= threshold:
                matched_patterns.append(
                    {
                        "intent": intent_label,
                        "pattern": original_pattern,
                        "score": score,
                    }
                )

        if best_score < threshold:
            best_intent = "invalid"
            best_score = 0.0

        return best_intent, best_score, matched_patterns

    def get_responses(self, intent_name, product_type=None):
        if intent_name not in self.intents_data:
            return ["I'm sorry, I don't have a response for that."]

        responses = self.intents_data[intent_name]["responses"]

        if intent_name == "product_selection" and product_type:
            if isinstance(responses, dict) and product_type in responses:
                return responses[product_type]
            else:
                return [
                    "I'm sorry, I don't have specific information for that product type."
                ]
        elif isinstance(responses, list):
            return responses
        else:
            return [
                "I'm sorry, I need more information to provide a specific response."
            ]


# Initialize IntentRecognizer
intent_recognizer = IntentRecognizer()

# Assign extractor and validation functions to the lead capture flow template
# Pass the nlp model from intent_recognizer to extract_name
LEAD_CAPTURE_FLOW_TEMPLATE.questions[0].extractor = lambda text: extract_name(
    text, intent_recognizer.nlp
)
LEAD_CAPTURE_FLOW_TEMPLATE.questions[1].validation = is_valid_email


class Chatbot:
    def __init__(self, session_id: str, min_overall_confidence=0.7):
        self.session_id = session_id
        self.context = cache.get_context(self.session_id)
        self.min_overall_confidence = min_overall_confidence

    @property
    def last_intent(self) -> str | None:
        return self.context.get("last_intent")

    @last_intent.setter
    def last_intent(self, intent: str | None):
        self.context["last_intent"] = intent

    def get_response(self, user_input: str) -> str:
        if not isinstance(user_input, str) or not user_input.strip():
            return random.choice(intent_recognizer.get_responses("invalid"))

        if any(keyword in user_input.lower() for keyword in EXIT_KEYWORDS):
            active_flow = self.context.get("conversation_flow")
            if active_flow and active_flow.is_active:
                active_flow.deactivate()
                self.last_intent = "invalid"
                return "Okay, cancelling that. What would you like to do?"

        intent, confidence, matched_patterns = self._recognize_intent(user_input)

        active_flow = self.context.get("conversation_flow")
        if active_flow and active_flow.is_active:
            if intent != self.last_intent and intent not in [
                "affirmative",
                "invalid",
                "product_selection",
            ]:
                active_flow.deactivate()
            else:
                response = active_flow.process_answer(user_input, self.context)
                if response:
                    return response

        if self.last_intent == "product_info" and intent == "product_selection":
            # This block might need refinement based on how product_selection is handled by IntentRecognizer
            # For now, we'll rely on the intent_recognizer to handle product selection responses
            pass  # The intent_recognizer should handle this now

        if intent == "affirmative" and self.last_intent == "product_info":
            self.last_intent = "product_info_affirmative"
            return "Great! Which product are you interested in: AI-Powered Analytics, Cloud Services, or Cybersecurity?"

        if intent == "lead_capture_start":
            if self.context.get("lead_captured"):
                return "I already have your contact information. A sales representative will be in touch soon."

            new_flow = ConversationFlow(
                list(LEAD_CAPTURE_FLOW_TEMPLATE.questions),
                LEAD_CAPTURE_FLOW_TEMPLATE.completion_message,
            )
            self.context["conversation_flow"] = new_flow
            question = new_flow.get_current_question()
            self.last_intent = intent
            return question.text if question else "Something went wrong."

        if intent and intent != "invalid":
            responses = intent_recognizer.get_responses(intent)
            if isinstance(responses, list) and responses:
                self.last_intent = intent
                return random.choice(responses)

        if intent == "help":
            # This logic needs to be updated to use intent_recognizer.intents_data
            capabilities = []
            for key, data in intent_recognizer.intents_data.items():
                if key not in [
                    "invalid",
                    "affirmative",
                    "help",
                    "product_selection",
                    "lead_capture_start",
                ] and data.get("patterns"):
                    capabilities.append(key.replace("_", " "))
            if capabilities:
                return f"I can help you with: {', '.join(capabilities)}. What would you like assistance with?"
            else:
                return (
                    "I'm a simple chatbot right now, but I can answer basic questions."
                )

        self.last_intent = intent
        return random.choice(intent_recognizer.get_responses("invalid"))

    def _recognize_intent(self, user_input: str) -> tuple[str, float, list]:
        # Use the new IntentRecognizer class
        intent, confidence, matched_patterns = intent_recognizer.recognize_intent(
            user_input, threshold=self.min_overall_confidence
        )
        print(f"--- Intent Recognition for: '{user_input}' ---")
        print(f"  Recognized Intent: '{intent}' (Confidence: {confidence:.2f})")

        # Extract entities using the nlp model from intent_recognizer
        extracted_ents = extract_entities(user_input.lower(), intent_recognizer.nlp)
        # You can use extracted_ents here if needed for further logic, but for now,
        # the primary intent recognition is handled by IntentRecognizer.

        return intent, confidence, matched_patterns
