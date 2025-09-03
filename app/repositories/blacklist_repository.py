from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blacklist import Blacklist
from app.core.utils.phone import to_e164


class BlacklistRepository:
    """Repository for managing blacklist records with E.164 normalization."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def is_blacklisted(self, phone_raw: str, region: str = "DE") -> bool:
        phone = phone_raw if phone_raw.startswith("+") else to_e164(phone_raw, region)
        result = await self.db_session.execute(
            select(Blacklist.id).where(Blacklist.phone_number == phone)
        )
        return result.scalar() is not None

    async def add(self, phone_raw: str, region: str = "DE") -> str:
        phone = phone_raw if phone_raw.startswith("+") else to_e164(phone_raw, region)
        if not await self.is_blacklisted(phone):
            self.db_session.add(Blacklist(phone_number=phone))
            await self.db_session.commit()
        return phone

    async def remove(self, phone_raw: str, region: str = "DE") -> str:
        phone = phone_raw if phone_raw.startswith("+") else to_e164(phone_raw, region)
        await self.db_session.execute(
            delete(Blacklist).where(Blacklist.phone_number == phone)
        )
        await self.db_session.commit()
        return phone


