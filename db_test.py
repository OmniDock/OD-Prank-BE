import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
import dotenv
from sqlalchemy import text

dotenv.load_dotenv('.env.local')

def patch_url(url: str) -> str:
    if url.startswith('postgresql://'):
        return url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql+asyncpg://', 1)
    return url

async def test():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print('DATABASE_URL not set!')
        return
    db_url = patch_url(db_url)
    print('Using DB URL:', db_url)
    engine = create_async_engine(
        db_url,
        poolclass=NullPool,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        }
        )
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text('SELECT 1'))
        print('DB CONNECTED, result:', result.scalar())
    except Exception as e:
        print('DB CONNECTION FAILED:', e)
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test())
