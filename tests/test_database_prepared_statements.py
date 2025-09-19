import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.database import create_session_maker_for_worker


@pytest.mark.asyncio
async def test_duplicate_prepared_statements_do_not_occur():
    if ".pooler." not in settings.DATABASE_URL and not settings.DATABASE_URL.rstrip("/").endswith(":6543"):
        pytest.skip("Test only relevant when using PgBouncer transaction pooler")

    session_maker, engine = create_session_maker_for_worker()

    try:
        for _ in range(4):
            async with session_maker() as session:
                result = await session.execute(text("SELECT 1"))
                value = result.scalar_one()
                assert value == 1
    finally:
        await engine.dispose()
