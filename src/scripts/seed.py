import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from sqlmodel import Session, SQLModel, create_engine

from src.core.config import settings
from src.helpers.auth import hash_password
from src.models.contexts import ContextCategory, Contexts
from src.models.forms import FormQuestions, Forms, FormSections
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
}

sections_data = [
    {"title": "Customer Info", "order": 1},
    {"title": "Job Details", "order": 2},
    {"title": "Preferences", "order": 3},
]

questions_data = {
    "Customer Info": [
        {
            "description": "This question asks for the full legal name of the customer, including first, middle, and last names. The response should be the complete name as it appears on official documents or identification. It is crucial for identifying the customer and personalizing future interactions. The input should be a non-empty string containing at least one name field.",
            "prompt": "What is your full name?",
            "required": True,
            "order": 1,
        },
        {
            "description": "This question asks for the customer's phone number, which should be in a valid format, typically including a country code, area code, and local number. This is necessary for communication regarding the job. The response should be a valid phone number (e.g., +1-555-1234 or 555-1234).",
            "prompt": "Could you please provide your phone number?",
            "required": True,
            "order": 2,
        },
    ],
    "Job Details": [
        {
            "description": "This question confirms whether the painting job is for the exterior of the property. A 'Yes' answer indicates that the job will involve exterior surfaces, while 'No' means the job will be for indoor areas. The expected input is either 'Yes' or 'No'.",
            "prompt": "Is the paint job for the exterior of your property?",
            "required": True,
            "order": 1,
        },
        {
            "description": "This optional question asks if the customer has a preferred start date for the painting job. If provided, the date should be in the format 'YYYY-MM-DD', or the customer can indicate an expression such as 'As soon as possible' or 'No preference'. If no date is provided, the company will follow up to suggest available options.",
            "prompt": "Do you have a preferred date for the job to start?",
            "required": False,
            "order": 2,
        },
    ],
    "Preferences": [
        {
            "description": "This question asks the customer about their preferred paint finish. The answer will help determine the look and durability of the job. Common options include matte (flat), eggshell (low sheen), satin, semi-gloss, and glossy. The expected input is a string describing the paint finish, such as 'Matte', 'Eggshell', 'Glossy', etc.",
            "prompt": "What type of paint finish are you looking for? (Eg. Matte, Eggshell, or Glossy)",
            "required": True,
            "order": 1,
        },
        {
            "description": "This optional question allows the customer to list any colors they are considering for the paint job. Multiple colors can be listed, separated by commas. This information will help the service provider suggest appropriate color options or prepare swatches. The expected input is a comma-separated list of color names (e.g., 'Red, Blue, Light Gray').",
            "prompt": "Which colors are you considering? You can list multiple, separated by commas.",
            "required": False,
            "order": 2,
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
        # Create provider
        provider = Providers(
            email=provider_data["email"],
            first_name=provider_data["first_name"],
            last_name=provider_data["last_name"],
            password=provider_data["password"],
            phone_number=provider_data["phone_number"],
            is_verified=provider_data["is_verified"],
            access=provider_data["access"],
        )
        session.add(provider)
        session.commit()
        session.refresh(provider)

        # Create form
        form_embedding = (
            f"{form_data['name']}\n{form_data['type']}\n{form_data['description']}"
        )
        form = Forms(
            name=form_data["name"],
            type=form_data["type"],
            description=form_data["description"],
            created_by=provider.id,
            embedding=embeddings_model.embed_query(form_embedding),
        )
        session.add(form)
        session.commit()
        session.refresh(form)

        # Add sections and questions
        for section_info in sections_data:
            section_embedding = f"{section_info['title']}"
            section = FormSections(
                title=section_info["title"],
                order=section_info["order"],
                form_id=form.id,
                embedding=embeddings_model.embed_query(section_embedding),
            )
            session.add(section)
            session.commit()
            session.refresh(section)

            for question_info in questions_data[section.title]:
                question_embedding = (
                    f"{question_info['description']}\n{question_info['prompt']}"
                )
                if question_info.get("options"):
                    question_embedding += f"\n{','.join(question_info['options'])}"
                question = FormQuestions(
                    description=question_info["description"],
                    prompt=question_info["prompt"],
                    required=question_info["required"],
                    order=question_info["order"],
                    section_id=section.id,
                    embedding=embeddings_model.embed_query(question_embedding),
                )
                session.add(question)
                session.commit()

        # Add contexts
        for context_info in context_data:
            context = Contexts(
                name=context_info["name"],
                data=context_info["data"],
                category=context_info["category"],
                embedding=embeddings_model.embed_query(str(context_info["data"])),
                meta_data=context_info.get("meta_data"),
            )
            session.add(context)
            session.commit()

        print(
            "Database seeded successfully - Form, FormSection, FormQuestion, Provider, Context."
        )


if __name__ == "__main__":
    main()
