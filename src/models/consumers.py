from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import EmailStr
from pydantic.config import ConfigDict
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from helpers.model import BaseModel


class Consumers(BaseModel, table=True):
    email: EmailStr = Field(index=True, unique=True, max_length=320)
    name: str = Field(max_length=100)
    phone_number: str | None = None
    address: str | None = None
    active_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    meta_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))


class ConsumerCreate(SQLModel):
    email: EmailStr
    name: str
    phone_number: str | None = None
    address: str | None = None


class ConsumerRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

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
