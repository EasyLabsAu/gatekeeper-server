from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from helpers.model import BaseModel


class SessionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Sessions(BaseModel, table=True):
    consumer_id: UUID = Field(foreign_key="consumers.id")
    status: SessionStatus = Field(
        default=SessionStatus.PENDING,
        sa_column=Column(SAEnum(SessionStatus)),
    )
    transcription: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    initiated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    concluded_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    tags: list[str] | None = Field(
        default_factory=list,
        sa_column=Column(JSONB),
    )
    files: list[dict] | None = Field(
        default_factory=list,
        sa_column=Column(JSONB),
    )
    feedback: str | None = None
    rating: float | None = None
    meta_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))


class SessionCreate(SQLModel):
    consumer_id: UUID
    status: SessionStatus
    transcription: dict[str, Any]
    initiated_at: datetime
    concluded_at: datetime
    files: list[dict] | None = None
    tags: list[str] | None = None
    feedback: str | None = None
    rating: float | None = None


class SessionRead(SQLModel):
    id: UUID
    consumer_id: UUID
    status: SessionStatus
    files: list[dict] | None = None
    tags: list[str] | None = None
    feedback: str | None = None
    rating: float | None = None
    transcription: dict[str, Any]
    initiated_at: datetime
    concluded_at: datetime
    meta_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None


class SessionUpdate(SQLModel):
    consumer_id: UUID | None = None
    status: SessionStatus | None = None
    transcription: dict[str, Any] | None = None
    initiated_at: datetime | None = None
    concluded_at: datetime | None = None
    meta_data: dict[str, Any] | None = None
    active_at: datetime | None = None


class SessionQuery(BaseModel):
    tags: list[str] | None = None
    status: SessionStatus | None = None
    initiated_at: datetime | None = None
    concluded_at: datetime | None = None
