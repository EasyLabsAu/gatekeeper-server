from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from src.helpers.model import BaseModel


class Sessions(BaseModel, table=True):
    name: str
    context: str
    category: str
    embedding: str
    meta_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
