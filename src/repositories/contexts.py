from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.helpers.model import APIError, APIResponse
from src.helpers.repository import BaseRepository
from src.models.contexts import (
    ContextCreate,
    ContextQuery,
    ContextRead,
    Contexts,
    ContextUpdate,
)


class ContextRepository(BaseRepository):
    async def create(self, payload: ContextCreate) -> APIResponse[ContextRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            context = Contexts(**payload.model_dump())
            db.add(context)
            await db.commit()
            await db.refresh(context)
            data = ContextRead.model_validate(context)
            return APIResponse[ContextRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self,
        query: ContextQuery | None,
        skip: int = 0,
        limit: int = 20,
        exclude_deleted: bool = True,
    ) -> APIResponse[list[ContextRead]] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            filters = []
            if query and query.name:
                filters.append(Contexts.name == query.name)
            if exclude_deleted and hasattr(Contexts, "is_deleted"):
                filters.append(Contexts.is_deleted == False)  # noqa: E712

            statement = select(Contexts)
            if filters:
                statement = statement.where(*filters)
            statement = statement.offset(skip).limit(limit)
            result = await db.execute(statement)
            contexts = result.scalars().all()
            data = [ContextRead.model_validate(session) for session in contexts]
            return APIResponse[list[ContextRead]](
                data=data,
                meta={"skip": skip, "limit": limit, "count": len(data)},
            )
        finally:
            await self.close_database_session()

    async def get(
        self, id: UUID, include_deleted: bool = False
    ) -> APIResponse[ContextRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Contexts).where(Contexts.id == id)
            if not include_deleted and hasattr(Contexts, "is_deleted"):
                statement = statement.where(Contexts.is_deleted == False)  # noqa: E712
            result = await db.execute(statement)
            context = result.scalar_one_or_none()
            if not context:
                raise APIError(404, "Session not found")
            data = ContextRead.model_validate(context)
            return APIResponse[ContextRead](data=data)
        finally:
            await self.close_database_session()

    async def update(
        self, id: UUID, payload: ContextUpdate
    ) -> APIResponse[ContextRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Contexts).where(
                Contexts.id == id,
                (Contexts.is_deleted == False)  # noqa: E712
                if hasattr(Contexts, "is_deleted")
                else True,
            )
            result = await db.execute(statement)
            context = result.scalar_one_or_none()
            if not context:
                raise APIError(404, "Session not found")
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(context, key, value)
            db.add(context)
            await db.commit()
            await db.refresh(context)
            data = ContextRead.model_validate(context)
            return APIResponse[ContextRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def delete(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Contexts).where(
                Contexts.id == id,
                (Contexts.is_deleted == False)  # noqa: E712
                if hasattr(Contexts, "is_deleted")
                else True,
            )
            result = await db.execute(statement)
            context = result.scalar_one_or_none()
            if not context:
                raise APIError(404, "Session not found")
            if hasattr(context, "soft_delete"):
                context.soft_delete()
            elif hasattr(context, "is_deleted"):
                context.is_deleted = True
            else:
                raise APIError(400, "Soft delete not supported on Contexts model")
            db.add(context)
            await db.commit()
            return APIResponse(message="Session soft-deleted")
        finally:
            await self.close_database_session()
