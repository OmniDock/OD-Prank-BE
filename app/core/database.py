from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncEngine, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings

class Database:
    """Encapsulates all database-related logic."""

    def __init__(self):
        self.engine = self._create_async_engine()
        self.SessionLocal = async_sessionmaker(
            self.engine,
            autocommit=False,
            autoflush=False,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @staticmethod
    def _format_database_url(url: str) -> str:
        """Replace standard postgresql driver with the async driver."""
        return url.replace("postgresql://", "postgresql+asyncpg://").replace("postgres://", "postgresql+asyncpg://")

    @staticmethod
    def _needs_null_pool(db_url: str) -> bool:
        """Determine whether we must disable SQLAlchemy pooling for the given URL."""
        if settings.SQLALCHEMY_DISABLE_POOL:
            return True
        return ":6543/" in db_url  # Supabase transaction/shared poolers

    def _create_async_engine(self) -> AsyncEngine:
        """Create an AsyncEngine with settings tailored for Supabase + PgBouncer."""
        db_url = self._format_database_url(settings.DATABASE_URL)
        connect_args = {"statement_cache_size": 0, "prepared_statement_cache_size": 0}

        engine_kwargs = {
            "pool_pre_ping": True,
            "connect_args": connect_args,
        }
        if self._needs_null_pool(db_url):
            engine_kwargs["poolclass"] = NullPool

        return create_async_engine(db_url, **engine_kwargs)

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """Provides a transactional scope around a series of operations."""
        session = self.SessionLocal()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def dispose(self):
        """Dispose the engine and close all connections."""
        if self.engine:
            await self.engine.dispose()

db_manager = Database()

# FastAPI Dependency for injecting a session
async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Dependency that provides a session and handles cleanup."""
    async with db_manager.get_session() as session:
        yield session


# --- Additional helpers for app lifespan and worker processes ---

def lifespan_session():
    """Alias returning the process-local async session context manager."""
    return db_manager.get_session()

def create_engine(db_url: str | None = None) -> AsyncEngine:
    """Create a new AsyncEngine using the provided URL (defaults to settings.DATABASE_URL)."""
    target_url = Database._format_database_url(db_url or settings.DATABASE_URL)
    connect_args = {"statement_cache_size": 0, "prepared_statement_cache_size": 0}

    engine_kwargs = {
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }
    if Database._needs_null_pool(target_url):
        engine_kwargs["poolclass"] = NullPool

    return create_async_engine(target_url, **engine_kwargs)


def set_engine(engine: AsyncEngine) -> None:
    """Install a process-local engine and session maker for web requests."""
    db_manager.engine = engine
    db_manager.SessionLocal = async_sessionmaker(
        engine,
        autocommit=False,
        autoflush=False,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def dispose_engine() -> None:
    """Dispose the currently installed engine."""
    await db_manager.dispose()


def get_session_maker(engine: Optional[AsyncEngine] = None) -> async_sessionmaker[AsyncSession]:
    """Return an async sessionmaker bound to the provided engine, or the global one if omitted."""
    target = engine or db_manager.engine
    return async_sessionmaker(
        target,
        autocommit=False,
        autoflush=False,
        class_=AsyncSession,
        expire_on_commit=False,
    )
