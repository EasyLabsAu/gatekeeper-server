from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import EmailStr
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

from helpers.model import BaseModel

if TYPE_CHECKING:
    from models.sessions import Sessions


class Consumers(BaseModel, table=True):
    email: EmailStr = Field(index=True, unique=True, max_length=320)
    name: str = Field(max_length=100)
    phone_number: str | None = None
    address: str | None = None
    active_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    meta_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    # One consumer can have multiple sessions
    sessions: Mapped[list["Sessions"]] = Relationship(back_populates="consumer")


class ConsumerCreate(SQLModel):
    email: EmailStr
    name: str
    phone_number: str | None = None
    address: str | None = None


class ConsumerRead(SQLModel):
    id: UUID
    email: EmailStr
    name: str
    phone_number: str | None = None
    address: str | None = None
    meta_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None
    active_at: datetime | None


class ConsumerUpdate(SQLModel):
    email: EmailStr | None = None
    name: str | None = None
    phone_number: str | None = None
    address: str | None = None
    meta_data: dict[str, Any] | None = None
    active_at: datetime | None = None


class ConsumerQuery(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone_number: str | None = None
    address: str | None = None
