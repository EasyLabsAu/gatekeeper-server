import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from sqlmodel import Session, SQLModel, create_engine

from src.core.config import settings
from src.helpers.auth import hash_password
from src.models.forms import FormFieldTypes, FormQuestions, Forms, FormSections
from src.models.providers import ProviderAccess, Providers

# Sample data to be seeded
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
    "name": "Paint Job Request Form",
    "type": "survey",
    "description": "A form to collect details from homeowners about their paint job needs.",
    "chat_meta_data": {"welcome_message": "Hello! I'm here to help you with your paint job request. Let's get started!", "farewell_message": "Thank you for providing the details. We'll be in touch soon!"},
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
            "prompt": "Do you have a preferred date for the job to start? Please provide it in YYYY-MM-DD format.",
            "field_type": FormFieldTypes.DATETIME,
            "required": False,
            "order": 2,
        },
    ],
    "Preferences": [
        {
            "label": "Paint Finish Type",
            "prompt": "What type of paint finish are you looking for? (Matte, Eggshell, or Glossy)",
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


def main():
    """Seed the database with initial data."""
    engine = create_engine(str(settings.POSTGRES_URI))

    # Create all tables if they don't exist
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Create a sample provider
        provider = Providers(**provider_data)
        session.add(provider)
        session.commit()
        session.refresh(provider)

        # Create a sample form linked to the provider
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

        # Create sections and questions for the form
        for section_info in sections_data:
            section = FormSections(**section_info, form_id=form.id)
            session.add(section)
            session.commit()
            session.refresh(section)

            for question_info in questions_data[section.title]:
                question = FormQuestions(**question_info, section_id=section.id)
                session.add(question)
                session.commit()

        print("Database seeded successfully!")


if __name__ == "__main__":
    main()
