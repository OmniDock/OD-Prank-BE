# OD-Prank-BE/app/services/audio_preload_service.py
from typing import Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
import gc
from dataclasses import dataclass, asdict

from app.core.database import AsyncSession
from app.repositories.scenario_repository import ScenarioRepository
from app.services.tts_service import TTSService
from app.services.cache_service import CacheService
from app.models.voice_line import VoiceLine
from app.core.utils.enums import VoiceLineTypeEnum, VoiceLineAudioStatusEnum
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.logging import console_logger


@dataclass
class PreloadedAudio:
    """Container for preloaded audio data"""
    voice_line_id: int
    voice_line_type: VoiceLineTypeEnum
    order_index: int
    voice_id: str
    duration_ms: Optional[int]
    storage_path: str
    
class AudioPreloadService:
    """Service to preload and manage MP3 files in Redis cache for quick prank call access"""
    
    # Configuration
    _max_cache_age_minutes = 30  # TTL for cached audio metadata
    _max_concurrent_downloads = 5  # Limit concurrent downloads
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.tts_service = TTSService()
        self.scenario_repository = ScenarioRepository(db_session)
        
    @classmethod
    def _get_cache_key(cls, user_id: str, scenario_id: int) -> str:
        """Generate cache key for user-scenario combination"""
        return f"user_{user_id}_scenario_{scenario_id}"
    
    # Redis TTL handles expiration automatically, no cleanup needed
    

    async def preload_scenario_audio(self, user_id: str, scenario_id: int, preferred_voice_id: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Preload all available audio files for a scenario into memory
        
        Args:
            user_id: User ID for authentication and caching
            scenario_id: Scenario ID to preload
            
        Returns:
            Tuple[success: bool, message: str, stats: Dict[str, Any]]
        """
        try:
            cache = await CacheService.get_global()
            cache_key = self._get_cache_key(user_id, scenario_id)
            
            # Check if already preloaded in Redis
            cached_data = await cache.get_json(cache_key, prefix="audio:preload")
            if cached_data:
                console_logger.info(f"Audio already preloaded for {cache_key}")
                return True, f"Audio already preloaded"
            
            
            # Get scenario with voice lines and audio   
            query = select(VoiceLine).where(
                VoiceLine.scenario_id == scenario_id
            ).options(
                selectinload(VoiceLine.audios),
                selectinload(VoiceLine.scenario)
            ).order_by(VoiceLine.order_index)
            
            result = await self.db_session.execute(query)
            voice_lines = result.scalars().all()
            
            if not voice_lines:
                return False, f"No voice lines found for scenario {scenario_id}"
            
            # Verify user owns this scenario
            if str(voice_lines[0].scenario.user_id) != user_id:
                return False, "Unauthorized access to scenario"
            
            # Find ready audio files to preload
            audio_files_to_load = []
            
            for voice_line in voice_lines:
                # Choose most recent READY audio that matches preferred_voice_id if provided,
                # otherwise fallback to most recent READY audio.
                best_preferred = None
                best_any = None

                for audio in voice_line.audios:
                    if audio.status != VoiceLineAudioStatusEnum.READY:
                        continue

                    if best_any is None or audio.created_at > best_any.created_at:
                        best_any = audio

                    if preferred_voice_id and audio.voice_id == preferred_voice_id:
                        if best_preferred is None or audio.created_at > best_preferred.created_at:
                            best_preferred = audio

                chosen = best_preferred or best_any
                if chosen and chosen.storage_path:
                    audio_files_to_load.append((voice_line, chosen))
            
            if not audio_files_to_load:
                return False, "No ready audio files found for preloading"
            
            
            # Download audio files with concurrency limit
            preloaded_audio = {}
                
            for voice_line, audio in audio_files_to_load:   
                preloaded = PreloadedAudio(
                    voice_line_id=voice_line.id,
                    voice_line_type=voice_line.type,
                    order_index=voice_line.order_index,
                    voice_id=audio.voice_id,
                    duration_ms=audio.duration_ms,
                    storage_path=audio.storage_path
                )
                preloaded_audio[voice_line.id] = preloaded
            
            # Cache the results in Redis
            if preloaded_audio:
                # Convert PreloadedAudio objects to dicts for JSON serialization
                serializable_data = {
                    str(k): {
                        **asdict(v),
                        'voice_line_type': v.voice_line_type.value  # Enum to string
                    } for k, v in preloaded_audio.items()
                }
                
                # Store in Redis with TTL
                ttl_seconds = self._max_cache_age_minutes * 60
                await cache.set_json(
                    cache_key, 
                    serializable_data, 
                    ttl=ttl_seconds, 
                    prefix="audio:preload"
                )
                
                console_logger.info(f"Cached {len(preloaded_audio)} audio files for {cache_key}")
                return True, f"Successfully preloaded {len(preloaded_audio)} audio files"
            else:
                return False, "Failed to preload any audio files"
                
        except Exception as e:
            return False, f"Preload failed: {str(e)}"
    
    async def get_preloaded_audio(self, user_id: str, scenario_id: int, voice_line_id: Optional[int] = None) -> Optional[Dict[int, PreloadedAudio]]:
        """Get preloaded audio from Redis cache"""
        cache = await CacheService.get_global()
        cache_key = self._get_cache_key(user_id, scenario_id)
        
        # Get from Redis
        cached_data = await cache.get_json(cache_key, prefix="audio:preload")
        if not cached_data:
            return None
        
        # Convert back to PreloadedAudio objects
        preloaded_data = {}
        for str_id, audio_dict in cached_data.items():
            # Convert voice_line_type string back to enum
            audio_dict['voice_line_type'] = VoiceLineTypeEnum[audio_dict['voice_line_type']]
            preloaded_data[int(str_id)] = PreloadedAudio(**audio_dict)
        
        if voice_line_id is not None:
            if voice_line_id in preloaded_data:
                return {voice_line_id: preloaded_data[voice_line_id]}
            else:
                return None
        
        return preloaded_data
    
