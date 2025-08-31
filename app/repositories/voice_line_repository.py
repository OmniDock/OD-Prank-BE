from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
from app.models.voice_line import VoiceLine
from app.models.scenario import Scenario
from app.models.voice_line_audio import VoiceLineAudio
from app.core.logging import console_logger


class VoiceLineRepository:
    """Repository for voice line database operations"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def add_voice_lines(self, scenario_id: int, voice_lines_data: List[dict]) -> List[VoiceLine]:
        """Add voice lines to a scenario"""
        console_logger.info(f"Adding {len(voice_lines_data)} voice lines to scenario {scenario_id}")

        voice_lines: List[VoiceLine] = []
        for index, voice_line_data in enumerate(voice_lines_data):
            voice_line_data['scenario_id'] = scenario_id
            # order_index may already be set by caller; preserve if present
            if 'order_index' not in voice_line_data:
                voice_line_data['order_index'] = index
            voice_line = VoiceLine(**voice_line_data)
            self.db_session.add(voice_line)
            voice_lines.append(voice_line)

        await self.db_session.flush()

        for voice_line in voice_lines:
            await self.db_session.refresh(voice_line)

        console_logger.info(f"Added {len(voice_lines)} voice lines")
        return voice_lines

    async def get_voice_line_by_id_with_user_check(self, voice_line_id: int, user_id: str | UUID) -> Optional[VoiceLine]:
        """Get a voice line by ID with RLS check through scenario"""
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        console_logger.info(f"Getting voice line {voice_line_id} for user {user_id}")

        query = (
            select(VoiceLine)
            .join(Scenario)
            .where(VoiceLine.id == voice_line_id)
            .where(Scenario.user_id == user_id)
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_voice_lines_by_ids_with_user_check(self, voice_line_ids: List[int], user_id: str | UUID) -> List[VoiceLine]:
        """Get multiple voice lines by IDs with RLS check through scenario"""
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        console_logger.info(f"Getting voice lines {voice_line_ids} for user {user_id}")

        query = (
            select(VoiceLine)
            .join(Scenario)
            .where(VoiceLine.id.in_(voice_line_ids))
            .where(Scenario.user_id == user_id)
            .order_by(VoiceLine.order_index)
        )
        result = await self.db_session.execute(query)
        voice_lines = result.scalars().all()
        console_logger.info(f"Found {len(voice_lines)} voice lines out of {len(voice_line_ids)} requested")
        return voice_lines

    async def get_voice_lines_by_scenario_id(self, scenario_id: int) -> List[VoiceLine]:
        """Get all voice lines for a scenario (assumes scenario access already verified)"""
        console_logger.info(f"Getting voice lines for scenario {scenario_id}")

        query = (
            select(VoiceLine)
            .where(VoiceLine.scenario_id == scenario_id)
            .order_by(VoiceLine.order_index)
        )
        result = await self.db_session.execute(query)
        voice_lines = result.scalars().all()
        console_logger.info(f"Found {len(voice_lines)} voice lines for scenario {scenario_id}")
        return voice_lines

    async def update_voice_line_storage(self, voice_line_id: int, signed_url: str, storage_path: str, user_id: str | UUID) -> Optional[VoiceLine]:
        """Update voice line storage information with RLS check"""
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        console_logger.info(f"Updating storage for voice line {voice_line_id} for user {user_id}")

        # First, get the voice line with RLS check
        query = (
            select(VoiceLine)
            .join(Scenario)
            .where(VoiceLine.id == voice_line_id)
            .where(Scenario.user_id == user_id)
        )
        result = await self.db_session.execute(query)
        voice_line = result.scalar_one_or_none()

        if voice_line:
            # These attributes exist on a different model (VoiceLineAudio) in current design,
            # so this is a no-op for now unless fields are added to VoiceLine.
            # Kept for API compatibility if needed later.
            await self.db_session.flush()
            await self.db_session.refresh(voice_line)
            console_logger.info(f"Updated storage for voice line {voice_line_id}")
            return voice_line
        else:
            console_logger.warning(f"Voice line {voice_line_id} not found or access denied for user {user_id}")
            return None





