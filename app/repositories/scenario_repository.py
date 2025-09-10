from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, and_
from typing import List, Optional
from uuid import UUID
from app.models.scenario import Scenario
from app.models.voice_line import VoiceLine
from app.models.voice_line_audio import VoiceLineAudio
from app.core.utils.enums import VoiceLineAudioStatusEnum
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
    
    # Voice line operations moved to VoiceLineRepository
    
    async def get_scenario_by_id(self, scenario_id: int, user_id: str | UUID, load_audio: bool = False) -> Optional[Scenario]:
        """Get a scenario by ID with voice lines (with RLS check)
        
        Args:
            scenario_id: The scenario ID
            user_id: The user ID for RLS check
            load_audio: If True, also loads preferred audio for voice lines (expensive operation)
        """
        # Convert string to UUID if needed for database comparison
        if isinstance(user_id, str):
            user_id = UUID(user_id)
            
        
        # First, get the scenario with voice lines
        query = (
            select(Scenario)
            .options(selectinload(Scenario.voice_lines))
            .where(Scenario.id == scenario_id)
            .where(Scenario.user_id == user_id)  # RLS protection
        )
        
        result = await self.db_session.execute(query)
        scenario = result.scalar_one_or_none()
        
        if not scenario:
            return scenario
            
        # Only load audio if explicitly requested and scenario has a preferred voice
        if not load_audio or not scenario.preferred_voice_id:
            return scenario
        
        # Load the corresponding audios for all voice lines (only when needed for detail view)
        console_logger.debug(f"Loading preferred voice audios for scenario {scenario_id}")
        
        # Get all voice line IDs for this scenario
        voice_line_ids = [vl.id for vl in scenario.voice_lines]
        
        if voice_line_ids:
            # Query for READY audios that match the preferred voice
            audio_query = (
                select(VoiceLineAudio)
                .where(
                    and_(
                        VoiceLineAudio.voice_line_id.in_(voice_line_ids),
                        VoiceLineAudio.voice_id == scenario.preferred_voice_id,
                        VoiceLineAudio.status == VoiceLineAudioStatusEnum.READY
                    )
                )
            )
            
            audio_result = await self.db_session.execute(audio_query)
            audios = audio_result.scalars().all()
            
            # Create a mapping from voice_line_id to audio
            audio_map = {audio.voice_line_id: audio for audio in audios}
            
            # Attach the audio to each voice line for easy access
            for voice_line in scenario.voice_lines:
                if voice_line.id in audio_map:
                    # Temporarily store the preferred audio on the voice line object
                    voice_line._preferred_audio = audio_map[voice_line.id]
                    console_logger.debug(f"Attached preferred audio to voice line {voice_line.id}")
        
        return scenario
    
    async def get_user_scenarios(self, user_id: str | UUID, limit: int = 50, offset: int = 0, only_active: bool = True) -> List[Scenario]:
        """Get scenarios for a user"""
        # Convert string to UUID if needed
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        
        if only_active:
            query = (
                select(Scenario)
                .options(selectinload(Scenario.voice_lines))
                .where(Scenario.user_id == user_id)
                .where(Scenario.is_active == True)
                .order_by(Scenario.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        else:
            query = (
                select(Scenario)
                .options(selectinload(Scenario.voice_lines))
                .where(Scenario.user_id == user_id)
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

    # Voice line operations moved to VoiceLineRepository

    async def update_scenario_preferred_voice(self, scenario_id: int, user_id: str, preferred_voice_id: str) -> Optional[Scenario]:
        """Update scenario's preferred voice id with RLS check"""
        console_logger.info(f"Updating scenario {scenario_id} preferred_voice_id for user {user_id}")
        base_query = (
            select(Scenario)
            .where(Scenario.id == scenario_id)
            .where(Scenario.user_id == user_id)
        )
        result = await self.db_session.execute(base_query)
        scenario = result.scalar_one_or_none()
        if not scenario:
            console_logger.warning(f"Scenario {scenario_id} not found or access denied for user {user_id}")
            return None
        scenario.preferred_voice_id = preferred_voice_id
        await self.db_session.flush()
        # Ensure the change persists beyond this request
        await self.db_session.commit()
        
        # Re-load scenario with eager-loaded voice_lines to avoid MissingGreenlet during serialization
        reload_query = (
            select(Scenario)
            .options(selectinload(Scenario.voice_lines))
            .where(Scenario.id == scenario_id)
            .where(Scenario.user_id == user_id)
        )
        reloaded = await self.db_session.execute(reload_query)
        loaded_scenario = reloaded.scalar_one_or_none()
        return loaded_scenario or scenario
    
    async def delete_scenario(self, scenario_id: int, user_id: str | UUID) -> None:
        """Delete a scenario and all its related data
        
        Args:
            scenario_id: The scenario ID to delete
            user_id: The user ID for RLS check
        """
        # Convert string to UUID if needed for database comparison
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        
        # Get the scenario first to ensure it exists and belongs to the user
        query = select(Scenario).where(
            and_(
                Scenario.id == scenario_id,
                Scenario.user_id == user_id
            )
        )
        result = await self.db_session.execute(query)
        scenario = result.scalar_one_or_none()
        
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found or access denied")
        
        # Delete the scenario (cascade will handle related data)
        await self.db_session.delete(scenario)
        console_logger.info(f"Deleted scenario {scenario_id} for user {user_id}")
    
    async def get_public_scenarios(self) -> List[Scenario]:
        """Get all public scenarios (regardless of user)"""
        query = select(Scenario).where(Scenario.is_public == True)
        result = await self.db_session.execute(query)
        return result.scalars().all()