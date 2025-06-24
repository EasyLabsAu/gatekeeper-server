from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql.json import JSONB
from sqlmodel import Field, Relationship
from sqlmodel.main import SQLModel

from helpers.model import BaseModel
from models.sessions import Sessions


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
    name: str  # Title or name of the form
    type: str | None = None  # Type of the form (e.g., "feedback", "survey", etc.)
    description: str | None = None  # Optional description of the form
    created_by: UUID = Field(foreign_key="providers.id")
    meta_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    # One form can have multiple sections
    sections: list["FormSections"] = Relationship(back_populates="form")

    # One form can receive many user responses
    responses: list["FormResponses"] = Relationship(back_populates="form")


class FormCreate(SQLModel):
    name: str
    description: str | None = None
    type: str | None = None
    created_by: UUID


class FormRead(SQLModel):
    id: UUID
    name: str
    description: str | None = None
    type: str | None = None
    created_by: UUID
    meta_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None


class FormUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    type: str | None = None
    created_by: UUID | None = None
    concluded_at: datetime | None = None
    meta_data: dict[str, Any] | None = None
    active_at: datetime | None = None


class FormQuery(BaseModel):
    name: str | None = None
    description: str | None = None
    created_by: UUID | None = None
    type: str | None = None


# A form is divided into one or more sections
class FormSections(BaseModel, table=True, table_name="form_sections"):
    form_id: UUID = Field(foreign_key="forms.id")  # Reference to the parent form
    title: str  # Section title
    description: str | None = None  # Optional section description
    order: int  # Position of the section in the form

    # Back-reference to the parent form
    form: Forms = Relationship(back_populates="sections")

    # One section can have multiple questions
    questions: list["FormQuestions"] = Relationship(back_populates="section")


# Each section contains one or more questions
class FormQuestions(BaseModel, table=True, table_name="form_questions"):
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
class FormResponses(BaseModel, table=True, table_name="form_responses"):
    form_id: UUID = Field(foreign_key="forms.id")  # Reference to the original form
    session_id: UUID = Field(
        foreign_key="sessions.id"
    )  # Reference to the session this response belongs to
    submitted_at: str | None = None

    # Back-reference to the form that was answered
    form: Forms = Relationship(back_populates="responses")

    # One form response consists of multiple section responses
    section_responses: list["FormSectionResponses"] = Relationship(
        back_populates="form_response"
    )

    session: "Sessions" = Relationship(back_populates="form_responses")


# Stores user's answers for a specific section of a form
class FormSectionResponses(BaseModel, table=True, table_name="form_section_responses"):
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
class FormQuestionResponses(
    BaseModel, table=True, table_name="form_question_responses"
):
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
