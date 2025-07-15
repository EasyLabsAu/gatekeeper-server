from enum import Enum

from pydantic import BaseModel


class ChatType(str, Enum):
    ONBOARDING = "onboarding"
    OFFBOARDING = "offboarding"
    ENGAGEMENT = "engagement"


class Chat(BaseModel):
    type: ChatType
    client_id: str
    sender: str | None
    message: str | None
    timestamp: str | None
