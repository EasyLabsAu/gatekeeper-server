from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql.json import JSONB
from sqlmodel import Field
from sqlmodel.main import SQLModel

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
    name: str  # Title or name of the form
    type: str | None = None  # Type of the form (e.g., "feedback", "survey", etc.)
    description: str | None = None  # Optional description of the form
    created_by: UUID = Field(foreign_key="providers.id")
    meta_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))


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
    meta_data: dict[str, Any] | None = None
    active_at: datetime | None = None


class FormQuery(BaseModel):
    name: str | None = None
    created_by: UUID | None = None
    type: str | None = None


# A form is divided into one or more sections
class FormSections(BaseModel, table=True):
    form_id: UUID = Field(foreign_key="forms.id")  # Reference to the parent form
    title: str  # Section title
    description: str | None = None  # Optional section description
    order: int  # Position of the section in the form


class FormSectionsCreate(SQLModel):
    form_id: UUID
    title: str
    description: str | None = None
    order: int


class FormSectionsRead(SQLModel):
    id: UUID
    title: str
    description: str | None = None
    order: int
    form_id: UUID
    meta_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None


class FormSectionsUpdate(SQLModel):
    title: str | None = None
    form_id: UUID
    description: str | None = None
    order: int | None = None
    meta_data: dict[str, Any] | None = None


class FormSectionsQuery(BaseModel):
    form_id: UUID


# Each section contains one or more questions
class FormQuestions(BaseModel, table=True):
    section_id: UUID = Field(
        foreign_key="formsections.id"
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


class FormQuestionsCreate(SQLModel):
    section_id: UUID
    label: str
    field_type: FormFieldTypes
    required: bool
    order: int
    options: list[str]


class FormQuestionsRead(SQLModel):
    id: UUID
    section_id: UUID
    label: str
    field_type: FormFieldTypes
    required: bool
    options: list[str]
    order: int
    meta_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None


class FormQuestionsUpdate(SQLModel):
    section_id: UUID
    label: str | None = None
    field_type: FormFieldTypes | None = None
    order: int | None = None
    options: list[str] | None = None
    required: bool | None = None
    meta_data: dict[str, Any] | None = None


class FormQuestionsQuery(BaseModel):
    section_id: UUID | None = None


# Stores one user's overall submission of a form
class FormResponses(BaseModel, table=True):
    form_id: UUID = Field(foreign_key="forms.id")  # Reference to the original form
    session_id: UUID = Field(
        foreign_key="sessions.id"
    )  # Reference to the session this response belongs to
    submitted_at: str | None = None


class FormResponsesCreate(SQLModel):
    form_id: UUID
    session_id: UUID
    submitted_at: str | None = None


class FormResponsesRead(SQLModel):
    id: UUID
    form_id: UUID
    session_id: UUID
    submitted_at: str
    meta_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None


class FormResponsesUpdate(SQLModel):
    form_id: UUID
    session_id: UUID
    submitted_at: str | None = None
    meta_data: dict[str, Any] | None = None


class FormResponsesQuery(BaseModel):
    form_id: UUID | None = None
    session_id: UUID | None = None


# Stores user's answers for a specific section of a form
class FormSectionResponses(BaseModel, table=True):
    response_id: UUID = Field(
        foreign_key="formresponses.id"
    )  # Reference to overall form response
    section_id: UUID = Field(
        foreign_key="formsections.id"  # This now correctly references the table name
    )  # Reference to the section answered


class FormSectionResponsesCreate(SQLModel):
    response_id: UUID
    section_id: UUID


class FormSectionResponsesRead(SQLModel):
    id: UUID
    response_id: UUID
    section_id: UUID
    meta_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None


class FormSectionResponsesUpdate(SQLModel):
    response_id: UUID
    section_id: UUID
    meta_data: dict[str, Any] | None = None


class FormSectionResponsesQuery(BaseModel):
    response_id: UUID | None = None
    section_id: UUID | None = None


# Stores user's answer to a specific question in a section
class FormQuestionResponses(BaseModel, table=True):
    section_response_id: UUID = Field(
        foreign_key="formsectionresponses.id"
    )  # Which section this answer belongs to
    question_id: UUID = Field(
        foreign_key="formquestions.id"  # This now correctly references the table name
    )  # Which question this is an answer to

    # User's actual answer (can be string, number, datetime, etc. — stored as JSON)
    answer: str
    # Timestamp when the answer was submitted
    submitted_at: str | None = None


class FormQuestionResponsesCreate(SQLModel):
    section_response_id: UUID
    question_id: UUID
    answer: str
    submitted_at: str | None = None


class FormQuestionResponsesRead(SQLModel):
    id: UUID
    section_response_id: UUID
    question_id: UUID
    answer: str
    submitted_at: UUID
    meta_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None


class FormQuestionResponsesUpdate(SQLModel):
    section_response_id: UUID
    question_id: UUID
    answer: str
    submitted_at: UUID
    meta_data: dict[str, Any] | None = None


class FormQuestionResponsesQuery(BaseModel):
    section_response_id: UUID | None = None
    question_id: UUID | None = None
