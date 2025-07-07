import json
import pickle
from abc import ABC, abstractmethod
from typing import Any, TypeVar

import aioredis

from src.core.config import settings

T = TypeVar("T")


class SerializationStrategy(ABC):
    """Abstract base class for serialization strategies"""

    @abstractmethod
    def serialize(self, data: Any) -> str | bytes:
        pass

    @abstractmethod
    def deserialize(self, data: str | bytes) -> Any:
        pass


class JSONSerializer(SerializationStrategy):
    """JSON serialization strategy"""

    def serialize(self, data: Any) -> str:
        return json.dumps(data, default=str)

    def deserialize(self, data: str | bytes) -> Any:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data) if data else None


class PickleSerializer(SerializationStrategy):
    """Pickle serialization strategy for complex Python objects"""

    def serialize(self, data: Any) -> bytes:
        return pickle.dumps(data)

    def deserialize(self, data: str | bytes) -> Any:
        if isinstance(data, str):
            data = data.encode("utf-8")
        return pickle.loads(data) if data else None


class Cache:
    def __init__(
        self,
        redis_url: str = str(settings.REDIS_URI),
        serializer: SerializationStrategy = JSONSerializer(),
        key_prefix: str = "",
        default_ttl: int | None = None,
    ):
        self.redis = aioredis.from_url(
            redis_url,
            decode_responses=False,
        )
        self.redis_url = redis_url
        self.serializer = serializer or JSONSerializer()
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl

    async def connect(self):
        """Initialize Redis connection"""
        if not self.redis:
            self.redis = aioredis.from_url(
                self.redis_url,
                decode_responses=False,
            )

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()

    def _make_key(self, key: str) -> str:
        """Create a prefixed key"""
        return f"{self.key_prefix}:{key}" if self.key_prefix else key

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set a value with optional TTL"""
        await self.connect()
        redis_key = self._make_key(key)
        serialized_value = self.serializer.serialize(value)

        expiry = ttl or self.default_ttl
        if expiry:
            return await self.redis.setex(redis_key, expiry, serialized_value)
        else:
            return await self.redis.set(redis_key, serialized_value)

    async def get(self, key: str) -> Any:
        """Get a value by key"""
        await self.connect()
        redis_key = self._make_key(key)
        data = await self.redis.get(redis_key)
        return self.serializer.deserialize(data) if data else None

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys"""
        await self.connect()
        redis_keys = [self._make_key(key) for key in keys]
        return await self.redis.delete(*redis_keys)

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        await self.connect()
        redis_key = self._make_key(key)
        return bool(await self.redis.exists(redis_key))

    async def list_append(self, key: str, *values: Any) -> int:
        """Append values to a list"""
        await self.connect()
        redis_key = self._make_key(key)
        serialized_values = [self.serializer.serialize(v) for v in values]
        return await self.redis.rpush(redis_key, *serialized_values)

    async def list_get(self, key: str, start: int = 0, end: int = -1) -> list[Any]:
        """Get list items"""
        await self.connect()
        redis_key = self._make_key(key)
        items = await self.redis.lrange(redis_key, start, end)
        return [self.serializer.deserialize(item) for item in items]

    async def list_length(self, key: str) -> int:
        """Get list length"""
        await self.connect()
        redis_key = self._make_key(key)
        return await self.redis.llen(redis_key)

    async def hash_set(self, key: str, field: str, value: Any) -> int:
        """Set hash field"""
        await self.connect()
        redis_key = self._make_key(key)
        serialized_value = self.serializer.serialize(value)
        return await self.redis.hset(redis_key, field, serialized_value)

    async def hash_get(self, key: str, field: str) -> Any:
        """Get hash field"""
        await self.connect()
        redis_key = self._make_key(key)
        data = await self.redis.hget(redis_key, field)
        return self.serializer.deserialize(data) if data else None

    async def hash_get_all(self, key: str) -> dict[str, Any]:
        """Get all hash fields"""
        await self.connect()
        redis_key = self._make_key(key)
        data = await self.redis.hgetall(redis_key)
        return {
            field.decode()
            if isinstance(field, bytes)
            else field: self.serializer.deserialize(value)
            for field, value in data.items()
        }

    async def hash_delete(self, key: str, *fields: str) -> int:
        """Delete hash fields"""
        await self.connect()
        redis_key = self._make_key(key)
        return await self.redis.hdel(redis_key, *fields)

    async def set_add(self, key: str, *values: Any) -> int:
        """Add values to set"""
        await self.connect()
        redis_key = self._make_key(key)
        serialized_values = [self.serializer.serialize(v) for v in values]
        return await self.redis.sadd(redis_key, *serialized_values)

    async def set_members(self, key: str) -> list[Any]:
        """Get all set members"""
        await self.connect()
        redis_key = self._make_key(key)
        members = await self.redis.smembers(redis_key)
        return [self.serializer.deserialize(member) for member in members]

    async def keys(self, pattern: str = "*") -> list[str]:
        """Get keys matching pattern"""
        await self.connect()
        search_pattern = self._make_key(pattern)
        keys = await self.redis.keys(search_pattern)
        # Remove prefix from returned keys
        if self.key_prefix:
            prefix_len = len(self.key_prefix) + 1
            return [
                key.decode()[prefix_len:]
                if isinstance(key, bytes)
                else key[prefix_len:]
                for key in keys
            ]
        return [key.decode() if isinstance(key, bytes) else key for key in keys]

    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key"""
        await self.connect()
        redis_key = self._make_key(key)
        return await self.redis.expire(redis_key, ttl)

    async def ttl(self, key: str) -> int:
        """Get TTL for key"""
        await self.connect()
        redis_key = self._make_key(key)
        return await self.redis.ttl(redis_key)

    async def clear_prefix(self) -> int:
        """Clear all keys with the current prefix"""
        if not self.key_prefix:
            raise ValueError("Cannot clear without a key prefix")

        keys = await self.keys("*")
        if keys:
            return await self.delete(*keys)
        return 0
