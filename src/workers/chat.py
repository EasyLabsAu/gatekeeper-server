from uuid import UUID

from src.models.sessions import SessionUpdate
from src.repositories.sessions import SessionRepository


async def on_chat_updated(id: UUID, payload: SessionUpdate):
    repository = SessionRepository()
    await repository.update(id, payload)
