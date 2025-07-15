from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from src.helpers.model import BaseModel, utc_now


class SessionStatus(str, Enum):
    ACTIVE = "active"
    CONCLUDED = "concluded"
    DISCARDED = "discarded"


class Sessions(BaseModel, table=True):
    consumer_id: UUID | None = Field(foreign_key="consumers.id")
    form_id: UUID | None = Field(foreign_key="forms.id")
    status: SessionStatus = Field(
        default=SessionStatus.ACTIVE,
        sa_column=Column(SAEnum(SessionStatus)),
    )
    transcript: list[dict[str, Any]] = Field(
        default_factory=dict, sa_column=Column(JSONB)
    )
    activated_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True))
    )
    concluded_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    discarded_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    tags: list[str] | None = Field(
        default_factory=list,
        sa_column=Column(JSONB),
    )
    files: list[dict[str, Any]] | None = Field(
        default_factory=list,
        sa_column=Column(JSONB),
    )
    feedback: str | None = None
    rating: float | None = None
    meta_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))


class SessionCreate(SQLModel):
    consumer_id: UUID | None = None
    form_id: UUID | None = None
    status: SessionStatus = SessionStatus.ACTIVE
    transcript: list[dict[str, Any]]
    meta_data: dict[str, Any] | None = None
    files: list[dict[str, Any]] | None = None
    tags: list[str] | None = None
    feedback: str | None = None
    rating: float | None = None


class SessionRead(SQLModel):
    id: UUID
    consumer_id: UUID | None
    form_id: UUID | None
    status: SessionStatus
    files: list[dict[str, Any]] | None = None
    tags: list[str] | None = None
    feedback: str | None = None
    rating: float | None = None
    transcript: list[dict[str, Any]]
    activated_at: datetime
    concluded_at: datetime | None = None
    discarded_at: datetime | None = None
    meta_data: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None


class SessionUpdate(SQLModel):
    consumer_id: UUID | None = None
    form_id: UUID | None = None
    status: SessionStatus | None = None
    transcript: list[dict[str, Any]] | None = None
    activated_at: datetime | None = None
    concluded_at: datetime | None = None
    discarded_at: datetime | None = None
    meta_data: dict[str, Any] | None = None
    active_at: datetime | None = None


class SessionQuery(BaseModel):
    tags: list[str] | None = None
    consumer_id: UUID | None = None
    form_id: UUID | None = None
    status: SessionStatus | None = None
    activated_at: datetime | None = None
    concluded_at: datetime | None = None
