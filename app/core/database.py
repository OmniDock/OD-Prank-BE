from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from typing import AsyncGenerator
from app.core.config import settings


engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False, 
    future=True,
    connect_args={"statement_cache_size": 0},
    pool_size=5,            # max number of connections in the pool
    max_overflow=10,        # extra burst connections if needed
    pool_timeout=30,        # wait time before giving up
    pool_recycle=1800,      # recycle connections every 30 min
)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()