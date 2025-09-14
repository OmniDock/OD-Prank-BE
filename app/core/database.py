from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings
from contextlib import asynccontextmanager
import uuid
import os

DATABASE_URL = (
    settings.DATABASE_URL
    .replace("postgresql://", "postgresql+asyncpg://")
    .replace("postgres://", "postgresql+asyncpg://")
)

_ENGINE = None
_ENGINE_PID = None
_SESSION_MAKER = None

# Für Transaction Pooler (Port 6543) wären spezielle connect_args nötig (statement_cache_size=0),
# für Session Pooler/Direct Connection aber nicht!
def get_engine():
    global _ENGINE, _ENGINE_PID
    pid = os.getpid()
    if _ENGINE is None or _ENGINE_PID != pid:
        # Enforce SSL for Supabase session pooler on 5432
        connect_args = {}
        if ".supabase.com" in DATABASE_URL.lower():
            connect_args["ssl"] = True
        _ENGINE = create_async_engine(
            DATABASE_URL,
            poolclass=NullPool,  # oder: pool_size=5, max_overflow=0 für kleine Pools
            connect_args=connect_args or None,
        )
        _ENGINE_PID = pid
    return _ENGINE

def get_session_maker():
    global _SESSION_MAKER, _ENGINE_PID
    pid = os.getpid()
    if _SESSION_MAKER is None or _ENGINE_PID != pid:
        engine = get_engine()
        _SESSION_MAKER = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return _SESSION_MAKER

@asynccontextmanager
async def lifespan_session():
    """
    Provides a session for a request.
    Ensures commit/rollback happens properly, which is crucial for PgBouncer transaction pooling.
    """
    async with get_session_maker()() as session:  # type: AsyncSession
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            # Ensure session is closed (connection returned to pool)
            await session.close()

async def get_db_session():
    async with lifespan_session() as session:
        yield session