from enum import Enum

from pydantic import BaseModel


class ChatType(str, Enum):
    ONBOARDING = "onboarding"
    ENGAGEMENT = "engagement"


class Chat(BaseModel):
    type: ChatType
    client_id: str
    sender: str
    message: str
    form: str | None = None
    timestamp: str
