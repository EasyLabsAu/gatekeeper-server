from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from helpers.model import APIError, APIResponse
from helpers.repository import BaseRepository
from models.consumers import (
    ConsumerCreate,
    ConsumerQuery,
    ConsumerRead,
    Consumers,
    ConsumerUpdate,
)


class ConsumerRepository(BaseRepository):
    async def create(self, payload: ConsumerCreate) -> APIResponse[ConsumerRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Consumers).where(
                Consumers.email == payload.email,
            )
            result = await db.execute(statement)
            if result.scalar_one_or_none():
                raise APIError(409, "Consumer with this email already exists")

            consumer = Consumers(**payload.model_dump())
            db.add(consumer)
            await db.commit()
            await db.refresh(consumer)
            data = ConsumerRead.model_validate(consumer)
            return APIResponse[ConsumerRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self,
        query: ConsumerQuery,
        skip: int = 0,
        limit: int = 20,
    ) -> APIResponse[list[ConsumerRead]] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            filters = []
            if query.name:
                filters.append(Consumers.name == query.name)
            if query.email:
                filters.append(Consumers.email == query.email)
            if query.phone_number:
                filters.append(Consumers.phone_number == query.phone_number)
            if query.address:
                filters.append(Consumers.address == query.address)
            if hasattr(Consumers, "is_deleted"):
                filters.append(Consumers.is_deleted is False)  # noqa: E712

            statement = select(Consumers)
            if filters:
                statement = statement.where(*filters)
            statement = statement.offset(skip).limit(limit)
            result = await db.execute(statement)
            consumers = result.scalars().all()
            data = [ConsumerRead.model_validate(consumer) for consumer in consumers]
            return APIResponse[list[ConsumerRead]](
                data=data,
                meta={"skip": skip, "limit": limit, "count": len(data)},
            )
        finally:
            await self.close_database_session()

    async def get(self, id: UUID) -> APIResponse[ConsumerRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Consumers).where(Consumers.id == id)
            if hasattr(Consumers, "is_deleted"):
                statement = statement.where(Consumers.is_deleted is False)  # noqa: E712
            result = await db.execute(statement)
            consumer = result.scalar_one_or_none()
            if not consumer:
                raise APIError(404, "Consumer not found")
            data = ConsumerRead.model_validate(consumer)
            return APIResponse[ConsumerRead](data=data)
        finally:
            await self.close_database_session()

    async def update(
        self, id: UUID, payload: ConsumerUpdate
    ) -> APIResponse[ConsumerRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Consumers).where(Consumers.id == id)
            if hasattr(Consumers, "is_deleted"):
                statement = statement.where(Consumers.is_deleted is False)  # noqa: E712
            result = await db.execute(statement)
            consumer = result.scalar_one_or_none()
            if not consumer:
                raise APIError(404, "Consumer not found")
            update_data = payload.model_dump(exclude_unset=True)
            new_email = update_data.get("email")
            if new_email and new_email != consumer.email:
                email_check_statement = select(Consumers).where(
                    Consumers.email == new_email,
                    Consumers.id != id,
                )
                if hasattr(Consumers, "is_deleted"):
                    email_check_statement = email_check_statement.where(
                        Consumers.is_deleted is False  # noqa: E712
                    )
                email_check = await db.execute(email_check_statement)
                if email_check.scalar_one_or_none():
                    raise APIError(
                        409, "Another consumer with this email already exists"
                    )
            for key, value in update_data.items():
                setattr(consumer, key, value)
            db.add(consumer)
            await db.commit()
            await db.refresh(consumer)
            data = ConsumerRead.model_validate(consumer)
            return APIResponse[ConsumerRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def delete(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Consumers).where(Consumers.id == id)
            if hasattr(Consumers, "is_deleted"):
                statement = statement.where(Consumers.is_deleted is False)  # noqa: E712
            result = await db.execute(statement)
            consumer = result.scalar_one_or_none()
            if not consumer:
                raise APIError(404, "Consumer not found")
            if hasattr(Consumers, "soft_delete"):
                consumer.soft_delete()
            else:
                consumer.is_deleted = True  # fallback if soft_delete not implemented
            db.add(consumer)
            await db.commit()
            return APIResponse(message="Consumer soft-deleted")
        finally:
            await self.close_database_session()
