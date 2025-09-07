from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings
from contextlib import asynccontextmanager
import uuid 


DATABASE_URL = (
    settings.DATABASE_URL
    .replace("postgresql://", "postgresql+asyncpg://")
    .replace("postgres://", "postgresql+asyncpg://")
)

# engine = create_async_engine(
#     DATABASE_URL,
#     poolclass=NullPool,
#     connect_args={
#         "statement_cache_size": 0,
#     },
#     execution_options={"compiled_cache": None},
# )

engine = create_async_engine(
    url=DATABASE_URL,

    pool_recycle=3600,
    pool_pre_ping=True,
    connect_args={
        "prepare_threshold": None,
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
    },
)

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)






@asynccontextmanager
async def lifespan_session():
    """
    Provides a session for a request.
    Ensures commit/rollback happens properly, which is crucial for PgBouncer transaction pooling.
    """
    async with async_session_maker() as session:  # type: AsyncSession
        try:
            yield session
            # If no exception: commit
            await session.commit()
        except Exception:
            # Rollback on error
            await session.rollback()
            raise
        finally:
            # Ensure session is closed (connection returned to pool)
            await session.close()

async def get_db_session():
    async with lifespan_session() as session:
        yield session