import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Field, SQLModel


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
