import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from sqlmodel import Session, SQLModel, create_engine

from src.core.config import settings
from src.helpers.auth import hash_password
from src.models.contexts import ContextCategory, Contexts
from src.models.forms import FormFieldTypes, FormQuestions, Forms, FormSections
from src.models.providers import ProviderAccess, Providers

provider_data = {
    "email": "john@provider.com",
    "first_name": "John",
    "last_name": "Provider",
    "password": hash_password("john@provider.com"),
    "phone_number": "1234567890",
    "is_verified": True,
    "access": [ProviderAccess.READ_DATA, ProviderAccess.WRITE_DATA],
}

form_data = {
    "name": "Paint Job Request",
    "type": "survey",
    "description": "A form to collect details from homeowners about their paint job needs.",
    "chat_meta_data": {
        "welcome_message": "Hello! I'm here to help you with your paint job request. Let's get started!",
        "farewell_message": "Thank you for providing the details. We'll be in touch soon!",
    },
}

sections_data = [
    {"title": "Customer Info", "order": 1},
    {"title": "Job Details", "order": 2},
    {"title": "Preferences", "order": 3},
]

questions_data = {
    "Customer Info": [
        {
            "label": "Name",
            "prompt": "What is your full name?",
            "field_type": FormFieldTypes.TEXT,
            "required": True,
            "order": 1,
        },
        {
            "label": "Phone Number",
            "prompt": "Could you please provide your phone number?",
            "field_type": FormFieldTypes.NUMBER,
            "required": True,
            "order": 2,
        },
    ],
    "Job Details": [
        {
            "label": "Is this an exterior job?",
            "prompt": "Is the paint job for the exterior of your property?",
            "field_type": FormFieldTypes.BOOLEAN,
            "required": True,
            "order": 1,
            "options": ["Yes", "No"],
        },
        {
            "label": "Preferred Date",
            "prompt": "Do you have a preferred date for the job to start?",
            "field_type": FormFieldTypes.DATETIME,
            "required": False,
            "order": 2,
        },
    ],
    "Preferences": [
        {
            "label": "Paint Finish Type",
            "prompt": "What type of paint finish are you looking for? (Eg. Matte, Eggshell, or Glossy)",
            "field_type": FormFieldTypes.SINGLE_CHOICE,
            "required": True,
            "order": 1,
            "options": ["Matte", "Eggshell", "Glossy"],
        },
        {
            "label": "Colors You Like",
            "prompt": "Which colors are you considering? You can list multiple, separated by commas.",
            "field_type": FormFieldTypes.MULTIPLE_CHOICE,
            "required": False,
            "order": 2,
            "options": ["White", "Blue", "Green", "Yellow", "Gray"],
        },
    ],
}

context_data = [
    {
        "name": "Acme Co. Construction and Realty Overview",
        "data": """
                Company Name: Acme Co.
                Industry: Construction & Realty
                Services:
                - Residential Construction
                - Commercial Real Estate
                - Property Development
                - Renovations
                Locations: Perth, Sydney
                Projects Completed: 153
                """,
        "category": ContextCategory.INFORMATION,
        "meta_data": {
            "company_website": "https://www.acme.co",
        },
    },
    {
        "name": "Chatbot Communication Guidelines",
        "data": """
                Rule 1:
                - Rule: The chatbot cannot disclose its affiliation with 'Google' or any specific company. It should only state that it is an AI assistant designed to help with general customer support and inquiries.
                - Reason: To avoid customer confusion and to maintain brand neutrality.
                - Enforcement Level: Mandatory
                - Applies To: All chatbot interactions

                Rule 2:
                - Rule: If a customer asks for personal information, the chatbot must respond with: "I cannot provide personal details. If you need further assistance, please contact customer service directly."
                - Reason: To ensure privacy and comply with data protection regulations.
                - Enforcement Level: Mandatory
                - Applies To: All chatbot interactions

                Rule 3:
                - Rule: The chatbot should never make promises or claims about future product developments, availability, or services unless explicitly provided by official company communications.
                - Reason: To prevent miscommunication and ensure alignment with company policies.
                - Enforcement Level: Recommended
                - Applies To: All chatbot interactions
                """,
        "category": ContextCategory.RULE,
    },
    {
        "name": "Customer Support Chatbot Parameters",
        "data": """
                Parameter: Response Time Limit
                - Value: 10 seconds
                - Description: The maximum allowable time for the chatbot to respond to a user inquiry. This ensures quick engagement with users.
                - Default Value: 10 seconds
                - Acceptable Range: 5-15 seconds
                - Priority Level: High

                Parameter: Max Message Length
                - Value: 500 characters
                - Description: Defines the maximum length of a message that the chatbot can handle at once. Longer messages are truncated or split into multiple responses.
                - Default Value: 500 characters
                - Acceptable Range: 200-1000 characters
                - Priority Level: Medium

                Parameter: Language Support
                - Value: English
                - Description: Specifies which languages the chatbot can understand and respond in. This allows it to serve users from different regions.
                - Default Value: English
                - Acceptable Range: English
                - Priority Level: High

                Parameter: Error Handling Mode
                - Value: Graceful Degradation
                - Description: How the chatbot responds when an error occurs. 'Graceful Degradation' means the chatbot will apologize and provide a helpful fallback message.
                - Default Value: Graceful Degradation
                - Acceptable Range: Graceful Degradation, Error Notification, Self-recovery
                - Priority Level: High
                """,
        "category": ContextCategory.PARAMETER,
    },
]


def main():
    if settings.LLM_PROVIDER == "google_genai" and settings.LLM_KEY:
        os.environ["GOOGLE_API_KEY"] = settings.LLM_KEY
    else:
        raise ValueError(
            f"Unsupported LLM provider: {settings.LLM_PROVIDER} or no key provided."
        )

    engine = create_engine(str(settings.POSTGRES_URI))
    embeddings_model = GoogleGenerativeAIEmbeddings(model=settings.LLM_EMBEDDING_MODEL)

    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        provider = Providers(**provider_data)
        session.add(provider)
        session.commit()
        session.refresh(provider)

        form = Forms(
            name=form_data["name"],
            type=form_data["type"],
            description=form_data["description"],
            created_by=provider.id,
            chat_meta_data=form_data["chat_meta_data"],
        )
        session.add(form)
        session.commit()
        session.refresh(form)

        for section_info in sections_data:
            section = FormSections(**section_info, form_id=form.id)
            session.add(section)
            session.commit()
            session.refresh(section)

            for question_info in questions_data[section.title]:
                question = FormQuestions(**question_info, section_id=section.id)
                session.add(question)
                session.commit()

        for context_info in context_data:
            embedding = embeddings_model.embed_query(str(context_info["data"]))
            context = Contexts(
                name=context_info["name"],
                data=context_info["data"],
                category=context_info["category"],
                embedding=embedding,
                meta_data=context_info.get("meta_data"),
            )
            session.add(context)
            session.commit()

        print(
            "Database seeded successfully - Form, FormSection, FormQuestion, Provider, Context."
        )


if __name__ == "__main__":
    main()
