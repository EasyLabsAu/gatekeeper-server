from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import EmailStr
from pydantic.config import ConfigDict
from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSON
from sqlmodel import Field, SQLModel

from helpers.model import BaseModel


class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class UserBase(BaseModel):
    email: EmailStr = Field(index=True, unique=True, max_length=320)
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    role: UserRole = Field(
        default=UserRole.USER,
        sa_column=Column(SAEnum(UserRole)),
        description="User role options",
    )
    password: str = Field(repr=False)
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


class UserCreate(SQLModel):
    email: EmailStr
    first_name: str
    last_name: str
    password: str


class UserRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    meta_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None
    authenticated_at: datetime | None


class UserUpdate(SQLModel):
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    meta_data: dict[str, Any] | None = None
    authenticated_at: datetime | None = None


class UserQuery(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None


class UserValidate(SQLModel):
    email: EmailStr
    password: str


class UserRevalidate(SQLModel):
    refresh_token: str


class UserInvalidate(SQLModel):
    refresh_token: str


class UserManage(SQLModel):
    email: EmailStr
    new_email: EmailStr | None = None
    password: str | None = None
    new_password: str | None = None
    token: str | None = None


class UserManageAction(str, Enum):
    START_EMAIL_VERIFICATION = "start-email-verification"
    FINISH_EMAIL_VERIFICATION = "finish-email-verification"
    START_EMAIL_AUTHENTICATION = "start-email-authentication"
    FINISH_EMAIL_AUTHENTICATION = "finish-email-authentication"
    START_PASSWORD_RESET = "start-password-reset"
    FINISH_PASSWORD_RESET = "finish-password-reset"
    UPDATE_EMAIL = "update-email"
    UPDATE_PASSWORD = "update-password"


class UserAuthTokens(SQLModel):
    access_token: str
    refresh_token: str


class UserAuthRead(SQLModel):
    user: UserRead
    auth: UserAuthTokens


class UserManageRead(SQLModel):
    message: str


class Users(UserBase, table=True):
    meta_data: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
