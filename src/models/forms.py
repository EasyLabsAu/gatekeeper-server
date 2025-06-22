from enum import Enum
from uuid import UUID

from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, Relationship

from helpers.model import BaseModel


# Enum to define different types of form fields that a user can interact with
class FormFieldTypes(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"


# Main form container model
class Forms(BaseModel, table=True):
    __tablename__ = "forms"

    name: str  # Title or name of the form
    description: str | None = None  # Optional description of the form
    created_by: UUID = Field(
        foreign_key="providers.id"
    )  # Reference to the user who created the form

    # One form can have multiple sections
    sections: list["FormSections"] = Relationship(back_populates="form")

    # One form can receive many user responses
    responses: list["FormResponses"] = Relationship(back_populates="form")


# A form is divided into one or more sections
class FormSections(BaseModel, table=True):
    __tablename__ = "form_sections"

    form_id: UUID = Field(foreign_key="forms.id")  # Reference to the parent form
    title: str  # Section title
    description: str | None = None  # Optional section description
    order: int  # Position of the section in the form

    # Back-reference to the parent form
    form: Forms = Relationship(back_populates="sections")

    # One section can have multiple questions
    questions: list["FormQuestions"] = Relationship(back_populates="section")


# Each section contains one or more questions
class FormQuestions(BaseModel, table=True):
    __tablename__ = "form_questions"

    section_id: UUID = Field(
        foreign_key="form_sections.id"
    )  # Reference to the parent section
    label: str  # The question text shown to the user
    field_type: FormFieldTypes  # Type of the question (text, number, etc.)
    required: bool = False  # Whether the field is required
    order: int  # Position of the question within the section

    # For choice or multiple choice questions, these are the available options
    options: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(Text())),
        description="Applicable for single/multiple choice fields",
    )

    # Back-reference to the parent section
    section: FormSections = Relationship(back_populates="questions")


# Stores one user's overall submission of a form
class FormResponses(BaseModel, table=True):
    __tablename__ = "form_responses"

    form_id: UUID = Field(foreign_key="forms.id")  # Reference to the original form
    user_id: UUID  # User who submitted the form
    submitted_at: str | None = None

    # Back-reference to the form that was answered
    form: Forms = Relationship(back_populates="responses")

    # One form response consists of multiple section responses
    section_responses: list["FormSectionResponses"] = Relationship(
        back_populates="form_response"
    )


# Stores user's answers for a specific section of a form
class FormSectionResponses(BaseModel, table=True):
    __tablename__ = "form_section_responses"

    response_id: UUID = Field(
        foreign_key="form_responses.id"
    )  # Reference to overall form response
    section_id: UUID = Field(
        foreign_key="form_sections.id"
    )  # Reference to the section answered

    # Back-reference to the overall form response
    form_response: FormResponses = Relationship(back_populates="section_responses")

    # One section response includes multiple question responses
    question_responses: list["FormQuestionResponses"] = Relationship(
        back_populates="section_response"
    )


# Stores user's answer to a specific question in a section
class FormQuestionResponses(BaseModel, table=True):
    __tablename__ = "form_question_responses"

    section_response_id: UUID = Field(
        foreign_key="form_section_responses.id"
    )  # Which section this answer belongs to
    question_id: UUID = Field(
        foreign_key="form_questions.id"
    )  # Which question this is an answer to

    # User's actual answer (can be string, number, datetime, etc. — stored as JSON)
    answer: str
    # Timestamp when the answer was submitted
    submitted_at: str | None = None
    # Back-reference to the parent section response
    section_response: FormSectionResponses = Relationship(
        back_populates="question_responses"
    )
