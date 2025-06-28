from sqlmodel import Session, SQLModel, create_engine

from src.core.config import settings
from src.models.forms import FormFieldTypes, FormQuestions, Forms, FormSections
from src.models.providers import ProviderAccess, Providers

# Sample data to be seeded
provider_data = {
    "email": "john@provider.com",
    "first_name": "John",
    "last_name": "Doe",
    "password": "john@provider.com",
    "phone_number": "+1234567890",
    "is_verified": True,
    "access": [ProviderAccess.READ_DATA, ProviderAccess.WRITE_DATA],
}

form_data = {
    "name": "Paint Job Request Form",
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
            "label": "Name",
            "field_type": FormFieldTypes.TEXT,
            "required": True,
            "order": 1,
        },
        {
            "label": "Phone Number",
            "field_type": FormFieldTypes.NUMBER,
            "required": True,
            "order": 2,
        },
    ],
    "Job Details": [
        {
            "label": "Is this an exterior job?",
            "field_type": FormFieldTypes.BOOLEAN,
            "required": True,
            "order": 1,
            "options": ["Yes", "No"],
        },
        {
            "label": "Preferred Date",
            "field_type": FormFieldTypes.DATETIME,
            "required": False,
            "order": 2,
        },
    ],
    "Preferences": [
        {
            "label": "Paint Finish Type",
            "field_type": FormFieldTypes.SINGLE_CHOICE,
            "required": True,
            "order": 1,
            "options": ["Matte", "Eggshell", "Glossy"],
        },
        {
            "label": "Colors You Like",
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
