import json
import pickle
import random
from pathlib import Path
from uuid import UUID

import numpy as np
import spacy
from annoy import AnnoyIndex

from src.core.database import SessionFactory
from src.services.chatbot.helpers.flows import ConversationFlow, FormFlowManager
from src.services.chatbot.helpers.session import SessionManager
from src.services.chatbot.helpers.utils import (
    EXIT_KEYWORDS,
    LEAD_CAPTURE_FLOW_TEMPLATE,
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

    def get_responses(self, intent_name):
        if intent_name not in self.intents_data:
            return ["I'm sorry, I don't have a response for that."]

        responses = self.intents_data[intent_name]["responses"]

        if isinstance(responses, list):
            return responses
        else:
            return [
                "I'm sorry, I need more information to provide a specific response."
            ]


# Initialize IntentRecognizer
intent_recognizer = IntentRecognizer()
session_manager = SessionManager()

# Assign extractor and validation functions to the lead capture flow template
# Pass the nlp model from intent_recognizer to extract_name
LEAD_CAPTURE_FLOW_TEMPLATE.questions[0].extractor = lambda text: extract_name(
    text, intent_recognizer.nlp
)
LEAD_CAPTURE_FLOW_TEMPLATE.questions[1].validation = is_valid_email


class Chatbot:
    def __init__(self, session_id: str, min_overall_confidence=0.7):
        self.session_id = session_id
        self.context = {}
        self.min_overall_confidence = min_overall_confidence
        self.db_session = SessionFactory()
        self.form_flow_manager = FormFlowManager(self.db_session, session_manager)

    async def load_context(self):
        self.context = await session_manager.get_context(self.session_id)

    @property
    def last_intent(self) -> str | None:
        return self.context.get("last_intent")

    @last_intent.setter
    def last_intent(self, intent: str | None):
        self.context["last_intent"] = intent

    async def get_response(self, user_input: str) -> str:
        await self.load_context()
        response = ""
        try:
            if not isinstance(user_input, str) or not user_input.strip():
                response = random.choice(intent_recognizer.get_responses("invalid"))
                return response if response is not None else ""

            intent, confidence, matched_patterns = self._recognize_intent(user_input)

            if any(keyword in user_input.lower() for keyword in EXIT_KEYWORDS):
                active_flow = self.context.get("conversation_flow")
                if active_flow and active_flow.is_active:
                    active_flow.deactivate()
                    self.last_intent = "invalid"
                    response = "Okay, cancelling that. What would you like to do?"
                    return response if response is not None else ""

            active_flow = self.context.get("conversation_flow")
            if active_flow and active_flow.is_active:
                if self.context.get("current_form_id"):
                    is_valid_answer = await self.form_flow_manager.process_form_answer(
                        self.session_id, user_input
                    )
                    if not is_valid_answer:
                        self.context["invalid_answer_count"] += 1
                        if self.context["invalid_answer_count"] >= 3:
                            active_flow.deactivate()
                            self.context["invalid_answer_count"] = 0
                            response = "It seems you're having trouble. Let's try something else. What would you like to do?"
                        else:
                            response = "That doesn't seem right. Please try again."
                    else:
                        self.context["invalid_answer_count"] = 0
                        response = await self.form_flow_manager.get_next_question_text(
                            self.session_id
                        )

                    return response if response is not None else ""
                # Existing lead capture flow logic
                elif intent != self.last_intent and intent not in [
                    "affirmative",
                    "invalid",
                ]:
                    active_flow.deactivate()
                else:
                    flow_response = active_flow.process_answer(user_input, self.context)
                    if flow_response:
                        response = flow_response
                        return response if response is not None else ""

            if intent == "start_form_conversation":
                # TODO: Make this dynamic
                # For now, let's use a placeholder form_id. This will need to be dynamic.
                form_id_str = "954c2ec6-0ce9-43bd-888d-88a0a8347243"
                try:
                    form_id = UUID(form_id_str)
                except ValueError:
                    return "Invalid form ID provided."

                response = await self.form_flow_manager.start_form_conversation(
                    self.session_id, form_id
                )
                self.last_intent = intent
                return response if response is not None else ""

            if intent == "lead_capture_start":
                if self.context.get("lead_captured"):
                    response = "I already have your contact information. A sales representative will be in touch soon."
                    return response

                new_flow = ConversationFlow(
                    list(LEAD_CAPTURE_FLOW_TEMPLATE.questions),
                    LEAD_CAPTURE_FLOW_TEMPLATE.completion_message,
                )
                self.context["conversation_flow"] = new_flow
                question = new_flow.get_current_question()
                self.last_intent = intent
                response = question.text if question else "Something went wrong."
                return response

            if intent and intent != "invalid":
                responses = intent_recognizer.get_responses(intent)
                if isinstance(responses, list) and responses:
                    self.last_intent = intent
                    response = random.choice(responses)
                    return response

            if intent == "help":
                capabilities = []
                for key, data in intent_recognizer.intents_data.items():
                    if key not in [
                        "invalid",
                        "affirmative",
                        "help",
                    ] and data.get("patterns"):
                        capabilities.append(key.replace("_", " "))
                if capabilities:
                    response = f"I can help you with: {', '.join(capabilities)}. What would you like assistance with?"
                else:
                    response = "I'm a simple chatbot right now, but I can answer basic questions."
                return response

            self.last_intent = intent
            response = random.choice(intent_recognizer.get_responses("invalid"))
            return response
        finally:
            await session_manager.save_context(self.session_id, self.context)

    def _recognize_intent(self, user_input: str) -> tuple[str, float, list]:
        # Use the new IntentRecognizer class
        intent, confidence, matched_patterns = intent_recognizer.recognize_intent(
            user_input, threshold=self.min_overall_confidence
        )
        print(f"--- Intent Recognition for: '{user_input}' ---")
        print(f"  Recognized Intent: '{intent}' (Confidence: {confidence:.2f})")

        # Extract entities using the nlp model from intent_recognizer
        _ = extract_entities(user_input.lower(), intent_recognizer.nlp)
        # You can use extracted_ents here if needed for further logic, but for now,
        # the primary intent recognition is handled by IntentRecognizer.

        return intent, confidence, matched_patterns
