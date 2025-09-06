# from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
# from typing import AsyncGenerator
# from app.core.config import settings


# engine = create_async_engine(
#     settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
#     echo=False, 
#     future=True,
#     connect_args={"statement_cache_size": 0},
#     pool_size=5,            # max number of connections in the pool
#     max_overflow=10,        # extra burst connections if needed
#     pool_timeout=30,        # wait time before giving up
#     pool_recycle=1800,      # recycle connections every 30 min
# )

# async_session_maker = async_sessionmaker(
#     engine, class_=AsyncSession, expire_on_commit=False
# )


# async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
#     async with async_session_maker() as session:
#         try:
#             yield session
#         finally:
#             await session.close()


# from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
# from typing import AsyncGenerator
# from app.core.config import settings
# from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
# from sqlalchemy.pool import NullPool

# def _build_async_db_url_and_args(url: str):
#     split = urlsplit(url)
#     q = dict(parse_qsl(split.query, keep_blank_values=True))
#     sslmode = q.pop("sslmode", None)

#     # Rebuild URL without sslmode
#     split = split._replace(query=urlencode(q))
#     clean_url = urlunsplit(split)

#     # Ensure asyncpg driver
#     clean_url = (
#         clean_url.replace("postgresql://", "postgresql+asyncpg://")
#                  .replace("postgres://", "postgresql+asyncpg://")
#     )

#     # asyncpg connect args that work with PgBouncer (transaction pooling)
#     connect_args = {
#         "statement_cache_size": 0,             # legacy key
#         "prepared_statement_cache_size": 0,    # newer key
#     }

#     # # Map sslmode to asyncpg 'ssl' (optional; your DB may enforce TLS anyway)
#     # if sslmode:
#     #     if sslmode.lower() in ("disable", "0", "false"):
#     #         connect_args["ssl"] = False
#     #     else:
#     #         connect_args["ssl"] = True

#     return clean_url, connect_args

# db_url, connect_args = _build_async_db_url_and_args(settings.DATABASE_URL)

# engine = create_async_engine(
#     db_url,
#     echo=False,
#     future=True,
#     connect_args=connect_args,
#     poolclass=NullPool,
#     execution_options={"compiled_cache": None},
# )

# async_session_maker = async_sessionmaker(
#     engine, class_=AsyncSession, expire_on_commit=False
# )

# async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
#     async with async_session_maker() as session:
#         try:
#             yield session
#         finally:
#             await session.close()


from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings
from uuid import uuid4

DATABASE_URL = (
    settings.DATABASE_URL
    .replace("postgresql://", "postgresql+asyncpg://")
    .replace("postgres://", "postgresql+asyncpg://")
)


engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    }
)

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db_session():
    async with async_session_maker() as session:
        yield session