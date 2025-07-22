from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql.json import JSONB
from sqlmodel import Field, Relationship, SQLModel

from src.helpers.model import BaseModel

if TYPE_CHECKING:
    from src.models.providers import Providers
    from src.models.sessions import Sessions


# Main form container model
class Forms(BaseModel, table=True):
    name: str  # Title or name of the form
    type: str | None = None  # Type of the form (e.g., "feedback", "survey", etc.)
    description: str | None = None
    created_by: UUID = Field(foreign_key="providers.id")
    meta_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    embedding: list[float] | None = Field(default=None, sa_column=Column(Vector(768)))

    sections: list["FormSections"] = Relationship(
        back_populates="form", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
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
    meta_data: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None
    sections: list["FormSectionsRead"] = []


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
    embedding: list[float] | None = Field(default=None, sa_column=Column(Vector(768)))

    form: "Forms" = Relationship(back_populates="sections")
    questions: list["FormQuestions"] = Relationship(
        back_populates="section",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    responses: list["FormSectionResponses"] = Relationship(back_populates="section")


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
    created_at: datetime
    updated_at: datetime | None
    questions: list["FormQuestionsRead"] = []


class FormSectionsUpdate(SQLModel):
    title: str | None = None
    form_id: UUID
    description: str | None = None
    order: int | None = None


class FormSectionsQuery(BaseModel):
    form_id: UUID


# Each section contains one or more questions
class FormQuestions(BaseModel, table=True):
    section_id: UUID = Field(
        foreign_key="formsections.id"
    )  # Reference to the parent section
    prompt: str
    description: str
    required: bool = False
    order: int
    embedding: list[float] | None = Field(default=None, sa_column=Column(Vector(768)))

    section: "FormSections" = Relationship(back_populates="questions")
    responses: list["FormQuestionResponses"] = Relationship(back_populates="question")


class FormQuestionsCreate(SQLModel):
    section_id: UUID
    prompt: str
    description: str
    required: bool
    order: int


class FormQuestionsRead(SQLModel):
    id: UUID
    section_id: UUID
    prompt: str
    description: str
    required: bool
    order: int
    created_at: datetime
    updated_at: datetime | None


class FormQuestionsUpdate(SQLModel):
    section_id: UUID
    prompt: str | None = None
    description: str | None = None
    order: int | None = None
    required: bool | None = None


class FormQuestionsQuery(BaseModel):
    section_id: UUID | None = None


# Stores one user's overall submission of a form
class FormResponses(BaseModel, table=True):
    form_id: UUID = Field(foreign_key="forms.id")
    session_id: UUID = Field(foreign_key="sessions.id")
    submitted_at: datetime | None

    form: "Forms" = Relationship(back_populates="responses")
    section_responses: list["FormSectionResponses"] = Relationship(
        back_populates="response"
    )


class FormResponsesCreate(SQLModel):
    form_id: UUID
    session_id: UUID
    submitted_at: datetime | None


class FormResponsesRead(SQLModel):
    id: UUID
    form_id: UUID
    session_id: UUID
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class FormResponsesUpdate(SQLModel):
    form_id: UUID
    session_id: UUID
    submitted_at: datetime | None


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

    response: "FormResponses" = Relationship(back_populates="section_responses")
    section: "FormSections" = Relationship(back_populates="responses")
    question_responses: list["FormQuestionResponses"] = Relationship(
        back_populates="section_response"
    )


class FormSectionResponsesCreate(SQLModel):
    response_id: UUID
    section_id: UUID


class FormSectionResponsesRead(SQLModel):
    id: UUID
    response_id: UUID
    section_id: UUID
    created_at: datetime
    updated_at: datetime | None


class FormSectionResponsesUpdate(SQLModel):
    response_id: UUID
    section_id: UUID


class FormSectionResponsesQuery(BaseModel):
    response_id: UUID | None = None
    section_id: UUID | None = None


# Stores user's answer to a specific question in a section
class FormQuestionResponses(BaseModel, table=True):
    section_response_id: UUID = Field(foreign_key="formsectionresponses.id")
    question_id: UUID = Field(foreign_key="formquestions.id")
    answer: str
    submitted_at: datetime | None
    section_response: "FormSectionResponses" = Relationship(
        back_populates="question_responses"
    )
    question: "FormQuestions" = Relationship(back_populates="responses")


class FormQuestionResponsesCreate(SQLModel):
    section_response_id: UUID
    question_id: UUID
    answer: str
    submitted_at: datetime | None


class FormQuestionResponsesRead(SQLModel):
    id: UUID
    section_response_id: UUID
    question_id: UUID
    answer: str
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class FormQuestionResponsesUpdate(SQLModel):
    section_response_id: UUID
    question_id: UUID
    answer: str
    submitted_at: datetime | None


class FormQuestionResponsesQuery(BaseModel):
    section_response_id: UUID | None = None
    question_id: UUID | None = None


FormRead.model_rebuild()
FormSectionsRead.model_rebuild()
