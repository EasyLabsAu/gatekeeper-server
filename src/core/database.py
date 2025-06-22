import logging

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import select
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed

from core.config import settings
from helpers.logger import Logger

logger = Logger(__name__)

DATABASE_URI = str(settings.POSTGRES_URI)

# Create async engine with connection pooling
engine = create_async_engine(
    DATABASE_URI,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URI else {},
    echo=False,
)

# Create async session factory
SessionFactory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

max_tries = 60 * 5
wait_seconds = 1


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARN),
)
async def check_database_connection(db_engine: AsyncEngine) -> bool:
    """Health check for database connection."""
    try:
        TempSession = async_sessionmaker(db_engine, expire_on_commit=False)
        session = TempSession()
        await session.execute(select(1))
        logger.info("Database health check successful.")
        await session.close()
        return True
    except Exception as e:
        await session.close()
        logger.error(f"Database health check failed: {e}")
        return False
