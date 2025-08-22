from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from typing import List, Optional
from app.models.scenario import Scenario
from app.models.voice_line import VoiceLine
from app.core.logging import console_logger


class ScenarioRepository:
    """Repository for scenario database operations"""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def create_scenario(self, scenario_data: dict) -> Scenario:
        """Create a new scenario in the database"""
        console_logger.info(f"Creating scenario: {scenario_data.get('title')}")
        
        scenario = Scenario(**scenario_data)
        self.db_session.add(scenario)
        await self.db_session.flush()  # Get the ID without committing
        await self.db_session.refresh(scenario)
        
        console_logger.info(f"Created scenario with ID: {scenario.id}")
        return scenario
    
    async def add_voice_lines(self, scenario_id: int, voice_lines_data: List[dict]) -> List[VoiceLine]:
        """Add voice lines to a scenario"""
        console_logger.info(f"Adding {len(voice_lines_data)} voice lines to scenario {scenario_id}")
        
        voice_lines = []
        for index, voice_line_data in enumerate(voice_lines_data):
            voice_line_data['scenario_id'] = scenario_id
            voice_line_data['order_index'] = index 
            voice_line = VoiceLine(**voice_line_data)
            self.db_session.add(voice_line)
            voice_lines.append(voice_line)
        
        await self.db_session.flush()
        
        # Refresh all voice lines to get their IDs
        for voice_line in voice_lines:
            await self.db_session.refresh(voice_line)
        
        console_logger.info(f"Added {len(voice_lines)} voice lines")
        return voice_lines
    
    async def get_scenario_by_id(self, scenario_id: int, user_id: str) -> Optional[Scenario]:
        """Get a scenario by ID with voice lines (with RLS check)"""
        query = (
            select(Scenario)
            .options(selectinload(Scenario.voice_lines))
            .where(Scenario.id == scenario_id)
            .where(Scenario.user_id == user_id)  # RLS protection
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_scenarios(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Scenario]:
        """Get scenarios for a user"""
        query = (
            select(Scenario)
            .options(selectinload(Scenario.voice_lines))
            .where(Scenario.user_id == user_id)
            .where(Scenario.is_active == True)
            .order_by(Scenario.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        
        result = await self.db_session.execute(query)
        return result.scalars().all()
    
    async def commit(self):
        """Commit the current transaction"""
        await self.db_session.commit()
    
    async def rollback(self):
        """Rollback the current transaction"""
        await self.db_session.rollback()

    async def update_voice_line_text(self, voice_line_id: int, new_text: str, user_id: str) -> Optional[VoiceLine]:
        """Update the text of a specific voice line (with RLS check)"""
        console_logger.info(f"Updating voice line {voice_line_id} for user {user_id}")
        
        # First, get the voice line with RLS check through scenario
        query = (
            select(VoiceLine)
            .join(Scenario)
            .where(VoiceLine.id == voice_line_id)
            .where(Scenario.user_id == user_id)  # RLS protection
        )
        
        result = await self.db_session.execute(query)
        voice_line = result.scalar_one_or_none()
        
        if voice_line:
            voice_line.text = new_text
            await self.db_session.flush()
            await self.db_session.refresh(voice_line)
            console_logger.info(f"Updated voice line {voice_line_id}")
            return voice_line
        else:
            console_logger.warning(f"Voice line {voice_line_id} not found or access denied for user {user_id}")
            return None

    async def update_scenario_preferred_voice(self, scenario_id: int, user_id: str, preferred_voice_id: str) -> Optional[Scenario]:
        """Update scenario's preferred voice id with RLS check"""
        console_logger.info(f"Updating scenario {scenario_id} preferred_voice_id for user {user_id}")
        query = (
            select(Scenario)
            .where(Scenario.id == scenario_id)
            .where(Scenario.user_id == user_id)
        )
        result = await self.db_session.execute(query)
        scenario = result.scalar_one_or_none()
        if not scenario:
            console_logger.warning(f"Scenario {scenario_id} not found or access denied for user {user_id}")
            return None
        scenario.preferred_voice_id = preferred_voice_id
        await self.db_session.flush()
        await self.db_session.refresh(scenario)
        return scenario

    async def get_voice_line_by_id_with_user_check(self, voice_line_id: int, user_id: str) -> Optional[VoiceLine]:
        """Get a voice line by ID with RLS check through scenario"""
        console_logger.info(f"Getting voice line {voice_line_id} for user {user_id}")
        
        query = (
            select(VoiceLine)
            .join(Scenario)
            .where(VoiceLine.id == voice_line_id)
            .where(Scenario.user_id == user_id)  # RLS protection
        )
        
        result = await self.db_session.execute(query)
        voice_line = result.scalar_one_or_none()
        
        if voice_line:
            console_logger.info(f"Found voice line {voice_line_id}")
        else:
            console_logger.warning(f"Voice line {voice_line_id} not found or access denied for user {user_id}")
        
        return voice_line

    async def get_voice_lines_by_ids_with_user_check(self, voice_line_ids: List[int], user_id: str) -> List[VoiceLine]:
        """Get multiple voice lines by IDs with RLS check through scenario"""
        console_logger.info(f"Getting voice lines {voice_line_ids} for user {user_id}")
        
        query = (
            select(VoiceLine)
            .join(Scenario)
            .where(VoiceLine.id.in_(voice_line_ids))
            .where(Scenario.user_id == user_id)  # RLS protection
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

    async def update_voice_line_storage(self, voice_line_id: int, signed_url: str, storage_path: str, user_id: str) -> Optional[VoiceLine]:
        """Update voice line storage information with RLS check"""
        console_logger.info(f"Updating storage for voice line {voice_line_id} for user {user_id}")
        
        # First, get the voice line with RLS check
        voice_line = await self.get_voice_line_by_id_with_user_check(voice_line_id, user_id)
        
        if voice_line:
            voice_line.storage_url = signed_url
            voice_line.storage_path = storage_path
            await self.db_session.flush()
            await self.db_session.refresh(voice_line)
            console_logger.info(f"Updated storage for voice line {voice_line_id}")
            return voice_line
        else:
            console_logger.warning(f"Voice line {voice_line_id} not found or access denied for user {user_id}")
            return None
