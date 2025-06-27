import random
from datetime import datetime
from typing import Any

import nltk
import spacy
from spacy.language import Language

# Download NLTK data
nltk.download("punkt")

# Load spaCy model
nlp: Language | None = None
try:
    nlp = spacy.load("en_core_web_sm")
    print("spaCy model loaded successfully")
except OSError:
    # Model not found, try to download it
    print("spaCy model 'en_core_web_sm' not found. Attempting to download...")
    try:
        import subprocess
        import sys

        # Try to download using spaCy's download command
        subprocess.check_call(
            [sys.executable, "-m", "spacy", "download", "en_core_web_sm"]
        )
        nlp = spacy.load("en_core_web_sm")
        print("spaCy model downloaded and loaded successfully")
    except Exception as download_error:
        print(f"Failed to download spaCy model: {download_error}")
        print("To manually install the spaCy English model, run:")
        print("  pdm add pip  # if not already installed")
        print("  pdm run python -m spacy download en_core_web_sm")
        print("Using basic text processing instead of spaCy")
        nlp = None
except Exception as e:
    print(f"Error loading spaCy model: {e}")
    print("Using basic text processing instead of spaCy")
    nlp = None

# Define intents and responses
intents_data = {
    "greeting": {
        "patterns": ["hi", "hello", "hey", "hola", "greetings", "what's up"],
        "responses": [
            "Hello! How can I assist you today?",
            "Hi there! What can I help with?",
            "Greetings! How may I help you?",
        ],
    },
    "goodbye": {
        "patterns": ["bye", "goodbye", "see you later", "farewell"],
        "responses": [
            "Goodbye! Feel free to come back if you have more questions.",
            "Farewell! Have a great day!",
            "See you later!",
        ],
    },
    "thanks": {
        "patterns": ["thank", "thanks", "appreciate it"],
        "responses": [
            "You're welcome!",
            "Happy to help! Feel free to ask more questions.",
            "Anytime!",
        ],
    },
    "product_info": {
        "patterns": [
            "product information",
            "what products do you offer?",
            "tell me about your products",
            "products",
        ],
        "responses": [
            "We offer a wide range of technology solutions. Our main products include: \n"
            "- AI-Powered Analytics Suite\n- Cloud Infrastructure Repositorys\n- Cybersecurity Solutions\n",
            "Our product portfolio focuses on helping businesses increase efficiency and security. \n"
            "Would you like details about a specific product?",
        ],
    },
    "contact_us": {
        "patterns": [
            "how to contact",
            "your contact information",
            "contact details",
            "reach out",
        ],
        "responses": [
            "You can reach us at support@example.com or by calling (123) 456-7890.\n"
            "Our business hours are Monday to Friday, 9 AM to 5 PM.",
        ],
    },
    "need_lead_capture_name": {
        "patterns": ["what's your name"],
        "responses": [
            "Great! To proceed with our consultation, could you please provide your full name?"
        ],
    },
    "need_lead_capture_email": {
        "patterns": ["email", "what's your email"],
        "responses": ["Thank you! Now, please provide your email address."],
    },
    "need_lead_capture_phone": {
        "patterns": ["phone number", "how to reach you"],
        "responses": [
            "Perfect. Could you please share your phone number for follow-up?"
        ],
    },
    "invalid": {
        "patterns": [],  # Empty list instead of None
        "responses": [
            "I'm not sure I understand. Could you try asking differently?",
            "Could you please clarify your question?",
            "I didn't catch that. What would you like to know?",
        ],
    },
}

# Define entity labels
entity_labels = ["PRODUCT", "SERVICE", "COMPANY"]


class ChatEngine:
    def __init__(self):
        self.state: str | None = None  # Current conversation state/intent
        self.context: dict[str, Any] = {}  # Context store (e.g., collected lead info)
        # Initialize intents
        self.intents = dict(intents_data.items())

    def reset_conversation(self) -> str:
        """Reset the chatbot state/context"""
        self.state = None
        self.context = {}
        return "I've reset the conversation. How can I help you today?"

    def get_response(self, user_input: str) -> str:
        """Main function to process input and return output"""
        # 1. Preprocess user_input if needed (e.g., lowercase)
        cleaned_input = str(user_input).lower()

        # 2. Check if this is lead information being provided
        self.extract_lead_info(user_input, cleaned_input)

        # 3. Intent Recognition (Rule-based matching)
        self.state = self.recognize_intent(cleaned_input)

        # 4. Handle specific intents
        if self.state is None:
            response = self.handle_invalid_input(cleaned_input)
        else:
            # For lead generation, check collected items
            if self.state.startswith("need_lead_capture_"):
                response = self.handle_lead_capture(self.state)
            else:
                # Regular intent handling
                response = self.generate_response_for_state()

        return response

    def extract_lead_info(self, original_input: str, cleaned_input: str) -> None:
        """Extract lead information from user input"""
        # Extract name
        if (
            "name is" in cleaned_input
            or "my name" in cleaned_input
            or "i'm " in cleaned_input
        ):
            # Simple name extraction
            words = original_input.split()
            if "name is" in cleaned_input:
                idx = words.index("is") if "is" in words else -1
                if idx > -1 and idx + 1 < len(words):
                    self.context["info_name"] = " ".join(words[idx + 1 :]).rstrip(".")
            elif "my name" in cleaned_input:
                # Look for name after "my name is" or similar
                if "is" in words:
                    idx = words.index("is")
                    if idx + 1 < len(words):
                        self.context["info_name"] = " ".join(words[idx + 1 :]).rstrip(
                            "."
                        )

        # Extract email
        if "@" in original_input:
            words = original_input.split()
            for word in words:
                if "@" in word and "." in word:
                    self.context["info_email"] = word.rstrip(".")
                    break

        # Extract phone (simple pattern)
        import re

        phone_pattern = r"[\d\-\(\)\s]{10,}"
        phone_match = re.search(phone_pattern, original_input)
        if phone_match:
            self.context["info_phone"] = phone_match.group().strip()

    def recognize_intent(self, user_input: str) -> str | None:
        """Match the input against known intent patterns using both keyword matching and entity recognition"""
        if not user_input.strip():
            return None

        # First, try direct pattern matching
        for intent, data in self.intents.items():
            if (
                "patterns" in data and data["patterns"]
            ):  # Check if patterns exist and not empty
                patterns = data["patterns"]
                # Check for exact pattern matches
                for pattern in patterns:
                    if pattern.lower() == user_input.lower():
                        return intent

                # Check if any keyword exists in the input
                for pattern in patterns:
                    if pattern.lower() in user_input.lower():
                        return intent

        # Enhanced keyword matching for common business terms (fallback when spaCy not available)
        business_keywords = {
            "product_info": [
                "product",
                "repository",
                "offer",
                "sell",
                "buy",
                "purchase",
                "buying",
                "interested",
            ],
            "contact_us": [
                "contact",
                "phone",
                "email",
                "reach",
                "call",
                "support",
                "business hours",
                "hours",
            ],
            "greeting": ["hi", "hello", "hey", "greetings"],
            "goodbye": ["bye", "goodbye", "farewell", "exit"],
            "thanks": ["thank", "thanks", "appreciate"],
            "need_lead_capture_name": ["name is", "my name", "i'm", "call me"],
            "need_lead_capture_email": ["email is", "my email", "@"],
        }

        for intent, keywords in business_keywords.items():
            if any(keyword in user_input.lower() for keyword in keywords):
                return intent

        # If spaCy is available, try entity recognition
        if nlp is not None:
            doc = nlp(user_input)
            for ent in doc.ents:
                # Check if any predefined entity matches
                if ent.label_ in entity_labels:
                    for intent, data in self.intents.items():
                        if "patterns" in data and data["patterns"]:
                            for pattern in data["patterns"]:
                                if pattern.lower() == ent.text.lower():
                                    return intent

        # If all else fails, match by the most similar intent (catch-all)
        return "invalid"

    def generate_response_for_state(self) -> str:
        """Look up the response template for the current state"""
        if self.state is None:
            return self.handle_invalid_input("")

        intent_data = self.intents.get(self.state)
        if not intent_data or "responses" not in intent_data:
            # Fallback
            return self.handle_invalid_input("")

        response_templates = intent_data["responses"]

        # Get random response if multiple available
        if isinstance(response_templates, list) and len(response_templates) > 1:
            response_template = random.choice(response_templates)
        elif isinstance(response_templates, list) and len(response_templates) == 1:
            response_template = response_templates[0]
        else:
            response_template = str(response_templates)

        # Replace placeholders if needed (for dynamic data)
        for key, value in self.context.items():
            placeholder = f"{{{key}}}"
            if placeholder in response_template:
                # Format the value to make sense (e.g., date formatting)
                if key == "current_date" and isinstance(value, datetime):
                    formatted_value = value.strftime("%B %d, %Y")
                else:
                    formatted_value = str(value)
                response_template = response_template.replace(
                    placeholder, formatted_value
                )

        return response_template

    def handle_lead_capture(self, state_key: str) -> str:
        """Handle lead generation based on the specific capture stage"""
        # Check what information we have collected
        has_name = "info_name" in self.context
        has_email = "info_email" in self.context
        has_phone = "info_phone" in self.context

        # If we just captured name information
        if has_name and not has_email and state_key == "need_lead_capture_name":
            return f"Nice to meet you, {self.context['info_name']}! Could you please provide your email address so we can send you more information?"

        # If we just captured email information
        if has_email and not has_phone and state_key == "need_lead_capture_email":
            return f"Great! I have your email as {self.context['info_email']}. Could you also provide your phone number for our sales team to contact you?"

        # If we have all the information
        if has_name and has_email:
            return f"Perfect! Thank you {self.context['info_name']}. I have your email ({self.context['info_email']}) and our sales team will contact you within 24 hours with detailed product information."

        # Default responses based on state
        return self.generate_response_for_state()

    def handle_invalid_input(self, user_input: str) -> str:
        """Fallback function for unrecognized input"""
        return "I'm not sure I understand. Could you try asking in a different way or choose from our options?"
