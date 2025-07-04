import pickle
from typing import Any

import redis.asyncio as redis

from src.core.config import settings


class SessionManager:
    def __init__(
        self, host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0, expiration=86400
    ):
        self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=False)
        self.expiration = expiration

    async def get_context(self, session_id: str) -> dict[str, Any]:
        pickled_context = await self.redis.get(session_id)
        if pickled_context:
            context = pickle.loads(pickled_context)
            # Reset expiration on access
            await self.redis.expire(session_id, self.expiration)
            return context

        # Create a new session if one doesn't exist
        return {
            "conversation_flow": None,
            "lead_captured": False,
            "last_intent": None,
        }

    async def save_context(self, session_id: str, context: dict[str, Any]):
        pickled_context = pickle.dumps(context)
        await self.redis.setex(session_id, self.expiration, pickled_context)

    async def clear_session(self, session_id: str):
        await self.redis.delete(session_id)
