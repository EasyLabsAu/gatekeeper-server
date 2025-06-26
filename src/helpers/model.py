import uuid
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel as PydanticBaseModel
from sqlmodel import Field, SQLModel
from starlette.responses import JSONResponse

T = TypeVar("T")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BaseModel(SQLModel):
    """Base model with ID, timestamps, and soft delete functionality"""

    id: UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )

    # Timestamp fields
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime | None = Field(
        default=None, sa_column_kwargs={"onupdate": utc_now}
    )

    # Soft delete fields
    deleted_at: datetime | None = Field(default=None)
    is_deleted: bool = Field(default=False)

    def soft_delete(self) -> None:
        """Mark the record as deleted"""
        self.is_deleted = True
        self.deleted_at = utc_now()

    def restore(self) -> None:
        """Restore a soft-deleted record"""
        self.is_deleted = False
        self.deleted_at = None


class APIError(Exception):
    def __init__(
        self, status_code: int = 500, error: str = "An unknown error occurred"
    ):
        self.status_code = status_code
        self.error = error
        super().__init__(self.error)

    def response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={"error": self.error, "status_code": self.status_code},
        )


class APIResponse(PydanticBaseModel, Generic[T]):
    data: T | None = None
    message: str | None = None
    meta: dict[str, Any] | None = None
