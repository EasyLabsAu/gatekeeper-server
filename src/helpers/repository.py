from sqlalchemy.ext.asyncio import AsyncSession

from core.database import SessionFactory


class BaseRepository:
    def __init__(self):
        self._session: AsyncSession | None = None

    async def get_database_session(self) -> AsyncSession:
        if self._session is None:
            self._session = SessionFactory()
        return self._session

    async def close_database_session(self):
        if self._session:
            await self._session.close()
            self._session = None
