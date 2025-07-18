from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from src.helpers.model import BaseModel


class ContextCategory(str, Enum):
    RULE = "rule"
    PARAMETER = "parameter"
    INFORMATION = "information"


class Contexts(BaseModel, table=True):
    name: str
    data: str
    category: ContextCategory = Field(
        default=ContextCategory.INFORMATION,
        sa_column=Column(SAEnum(ContextCategory)),
    )
    embedding: list[float] | None = Field(default=None, sa_column=Column(Vector(768)))
    meta_data: dict[str, Any] | None = Field(
        default_factory=dict, sa_column=Column(JSONB)
    )


class ContextCreate(SQLModel):
    name: str
    data: str
    category: ContextCategory = ContextCategory.INFORMATION
    embedding: list[float] | None = None
    meta_data: dict[str, Any] | None = None


class ContextRead(SQLModel):
    id: UUID
    name: str
    data: str
    category: ContextCategory
    embedding: list[float] | None = None
    meta_data: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None


class ContextUpdate(SQLModel):
    name: str
    data: str
    category: ContextCategory
    embedding: list[float] | None = None
    meta_data: dict[str, Any] | None = None


class ContextQuery(BaseModel):
    name: str | None
    category: ContextCategory | None
