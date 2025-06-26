from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from helpers.model import APIError, APIResponse
from helpers.repository import BaseRepository
from models.sessions import (
    SessionCreate,
    SessionQuery,
    SessionRead,
    Sessions,
    SessionUpdate,
)


class SessionRepository(BaseRepository):
    async def create(self, payload: SessionCreate) -> APIResponse[SessionRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            session = Sessions(**payload.model_dump())
            db.add(session)
            await db.commit()
            await db.refresh(session)
            data = SessionRead.model_validate(session)
            return APIResponse[SessionRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self,
        query: SessionQuery,
        skip: int = 0,
        limit: int = 20,
        exclude_deleted: bool = True,
    ) -> APIResponse[list[SessionRead]] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            filters = []
            # NOTE: Advanced tag filtering for JSONB requires a custom SQL expression or post-query filtering.
            # For now, this will not filter by tags at the DB level.
            if query.status:
                filters.append(Sessions.status == query.status)
            if exclude_deleted and hasattr(Sessions, "is_deleted"):
                filters.append(Sessions.is_deleted is False)  # noqa: E712

            statement = select(Sessions)
            if filters:
                statement = statement.where(*filters)
            statement = statement.offset(skip).limit(limit)
            result = await db.execute(statement)
            sessions = result.scalars().all()
            # Post-query tag filtering (if needed)
            if query.tags:
                sessions = [
                    s
                    for s in sessions
                    if s.tags and any(tag in s.tags for tag in query.tags)
                ]
            data = [SessionRead.model_validate(session) for session in sessions]
            return APIResponse[list[SessionRead]](
                data=data,
                meta={"skip": skip, "limit": limit, "count": len(data)},
            )
        finally:
            await self.close_database_session()

    async def get(
        self, id: UUID, include_deleted: bool = False
    ) -> APIResponse[SessionRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Sessions).where(Sessions.id == id)
            if not include_deleted and hasattr(Sessions, "is_deleted"):
                statement = statement.where(Sessions.is_deleted is False)  # noqa: E712
            result = await db.execute(statement)
            session = result.scalar_one_or_none()
            if not session:
                raise APIError(404, "Session not found")
            data = SessionRead.model_validate(session)
            return APIResponse[SessionRead](data=data)
        finally:
            await self.close_database_session()

    async def update(
        self, id: UUID, payload: SessionUpdate
    ) -> APIResponse[SessionRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Sessions).where(
                Sessions.id == id,
                (Sessions.is_deleted is False)  # noqa: E712
                if hasattr(Sessions, "is_deleted")
                else True,
            )
            result = await db.execute(statement)
            session = result.scalar_one_or_none()
            if not session:
                raise APIError(404, "Session not found")
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(session, key, value)
            db.add(session)
            await db.commit()
            await db.refresh(session)
            data = SessionRead.model_validate(session)
            return APIResponse[SessionRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def delete(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Sessions).where(
                Sessions.id == id,
                (Sessions.is_deleted is False)  # noqa: E712
                if hasattr(Sessions, "is_deleted")
                else True,
            )
            result = await db.execute(statement)
            session = result.scalar_one_or_none()
            if not session:
                raise APIError(404, "Session not found")
            if hasattr(session, "soft_delete"):
                session.soft_delete()
            elif hasattr(session, "is_deleted"):
                session.is_deleted = True
            else:
                raise APIError(400, "Soft delete not supported on Sessions model")
            db.add(session)
            await db.commit()
            return APIResponse(message="Session soft-deleted")
        finally:
            await self.close_database_session()
