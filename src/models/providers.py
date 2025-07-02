from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import EmailStr
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from src.helpers.model import BaseModel


class ProviderAccess(str, Enum):
    READ_DATA = "read_data"
    WRITE_DATA = "write_data"
    DELETE_DATA = "delete_data"
    READ_USER = "read_user"
    WRITE_USER = "write_user"
    DELETE_USER = "delete_user"


class Providers(BaseModel, table=True):
    email: EmailStr = Field(index=True, unique=True, max_length=320)
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    access: list[ProviderAccess] = Field(
        default_factory=lambda: [ProviderAccess.READ_DATA],
        sa_column=Column(JSONB),
    )
    password: str = Field(repr=False)
    phone_number: str | None = None
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    verification_token: str | None = None
    verification_token_expires: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    authentication_token: str | None = None
    authentication_token_expires: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    reset_token: str | None = None
    reset_token_expires: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    authenticated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    meta_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))


class ProviderCreate(SQLModel):
    email: EmailStr
    first_name: str
    last_name: str
    password: str
    phone_number: str | None = None


class ProviderRead(SQLModel):
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    phone_number: str | None = None
    access: list[ProviderAccess]
    is_active: bool
    is_verified: bool
    meta_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None
    authenticated_at: datetime | None


class ProviderUpdate(SQLModel):
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    meta_data: dict[str, Any] | None = None
    authenticated_at: datetime | None = None


class ProviderQuery(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None


class ProviderValidate(SQLModel):
    email: EmailStr
    password: str


class ProviderRevalidate(SQLModel):
    refresh_token: str


class ProviderInvalidate(SQLModel):
    refresh_token: str


class ProviderManage(SQLModel):
    email: EmailStr
    new_email: EmailStr | None = None
    password: str | None = None
    new_password: str | None = None
    token: str | None = None


class ProviderManageAction(str, Enum):
    START_EMAIL_VERIFICATION = "start-email-verification"
    FINISH_EMAIL_VERIFICATION = "finish-email-verification"
    START_EMAIL_AUTHENTICATION = "start-email-authentication"
    FINISH_EMAIL_AUTHENTICATION = "finish-email-authentication"
    START_PASSWORD_RESET = "start-password-reset"
    FINISH_PASSWORD_RESET = "finish-password-reset"
    UPDATE_EMAIL = "update-email"
    UPDATE_PASSWORD = "update-password"


class ProviderAuthTokens(SQLModel):
    access_token: str
    refresh_token: str


class ProviderAuthRead(SQLModel):
    provider: ProviderRead
    auth: ProviderAuthTokens


class ProviderManageRead(SQLModel):
    message: str
