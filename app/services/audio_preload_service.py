# OD-Prank-BE/app/services/audio_preload_service.py
import asyncio
import aiohttp
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import weakref
import gc
from dataclasses import dataclass
import base64
import io
from pydub import AudioSegment
import audioop

from app.core.database import AsyncSession
from app.core.logging import console_logger
from app.repositories.scenario_repository import ScenarioRepository
from app.services.tts_service import TTSService
from app.models.voice_line import VoiceLine
from app.models.voice_line_audio import VoiceLineAudio
from app.core.utils.enums import VoiceLineTypeEnum, VoiceLineAudioStatusEnum
from sqlalchemy import select
from sqlalchemy.orm import selectinload


@dataclass
class PreloadedAudio:
    """Container for preloaded audio data"""
    voice_line_id: int
    voice_line_type: VoiceLineTypeEnum
    order_index: int
    audio_data: bytes
    voice_id: str
    duration_ms: Optional[int]
    size_bytes: int
    loaded_at: datetime
    storage_path: str
    # Precomputed for Telnyx streaming (optional)
    ulaw_chunks_b64: Optional[List[str]] = None
    ulaw_sample_rate_hz: Optional[int] = None
    ulaw_chunk_ms: Optional[int] = None


class AudioPreloadService:
    """Service to preload and manage MP3 files in memory for quick prank call access"""
    
    # Class-level cache to store preloaded audio sessions
    _preload_cache: Dict[str, Dict[int, PreloadedAudio]] = {}
    _cache_timestamps: Dict[str, datetime] = {}
    _max_cache_age_minutes = 30  # Auto-cleanup after 30 minutes
    _max_concurrent_downloads = 5  # Limit concurrent downloads
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.tts_service = TTSService()
        self.scenario_repository = ScenarioRepository(db_session)
        
    @classmethod
    def _get_cache_key(cls, user_id: str, scenario_id: int) -> str:
        """Generate cache key for user-scenario combination"""
        return f"user_{user_id}_scenario_{scenario_id}"
    
    @classmethod
    def _cleanup_expired_cache(cls):
        """Remove expired cache entries"""
        now = datetime.utcnow()
        expired_keys = []
        
        for cache_key, timestamp in cls._cache_timestamps.items():
            if now - timestamp > timedelta(minutes=cls._max_cache_age_minutes):
                expired_keys.append(cache_key)
        
        for key in expired_keys:
            if key in cls._preload_cache:
                audio_count = len(cls._preload_cache[key])
                total_size = sum(audio.size_bytes for audio in cls._preload_cache[key].values())
                console_logger.info(f"Cleaning up expired preload cache: {key} ({audio_count} files, {total_size:,} bytes)")
                del cls._preload_cache[key]
                del cls._cache_timestamps[key]
        
        # Force garbage collection if we cleaned up anything
        if expired_keys:
            gc.collect()
    
    async def _download_audio_file(self, storage_path: str, voice_line_id: int) -> Optional[bytes]:
        """Download audio file from Supabase storage"""
        try:
            # Get signed URL for the audio file
            signed_url = await self.tts_service.get_audio_url(storage_path, expires_in=3600)
            if not signed_url:
                console_logger.error(f"Failed to get signed URL for voice line {voice_line_id}")
                return None
            
            # Download the file
            async with aiohttp.ClientSession() as session:
                async with session.get(signed_url) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        console_logger.debug(f"Downloaded {len(audio_data):,} bytes for voice line {voice_line_id}")
                        return audio_data
                    else:
                        console_logger.error(f"Failed to download audio for voice line {voice_line_id}: HTTP {response.status}")
                        return None
                        
        except Exception as e:
            console_logger.error(f"Error downloading audio for voice line {voice_line_id}: {str(e)}")
            return None

    def _precompute_ulaw_chunks(self, mp3_bytes: bytes, *, chunk_ms: int = 40, sample_rate: int = 8000) -> Tuple[List[str], int, int]:
        """
        Prepare μ-law (PCMU) base64 chunks for smoother Telnyx streaming.
        - Downsample to 8kHz mono 16-bit PCM
        - Slice into chunk_ms windows (default 40ms for stability)
        - Convert each window to μ-law and base64-encode
        Returns: (chunks_b64, sample_rate, chunk_ms)
        """
        segment = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
        # Apply normalization and quality improvements
        segment = segment.set_frame_rate(sample_rate).set_channels(1).set_sample_width(2)
        # Normalize audio level for consistent volume
        segment = segment.normalize()
        
        chunks_b64: List[str] = []
        total_ms = len(segment)
        for start_ms in range(0, total_ms, chunk_ms):
            chunk = segment[start_ms:start_ms + chunk_ms]
            pcm16 = chunk.raw_data  # 16-bit LE PCM
            ulaw_bytes = audioop.lin2ulaw(pcm16, 2)
            chunks_b64.append(base64.b64encode(ulaw_bytes).decode("ascii"))
        return chunks_b64, sample_rate, chunk_ms
    
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
            # Cleanup expired cache first
            self._cleanup_expired_cache()
            
            cache_key = self._get_cache_key(user_id, scenario_id)
            
            # Check if already preloaded and not expired
            if cache_key in self._preload_cache:
                cached_time = self._cache_timestamps.get(cache_key, datetime.min)
                if datetime.utcnow() - cached_time < timedelta(minutes=self._max_cache_age_minutes):
                    audio_count = len(self._preload_cache[cache_key])
                    total_size = sum(audio.size_bytes for audio in self._preload_cache[cache_key].values())
                    return True, f"Audio already preloaded ({audio_count} files)", {
                        "cached": True,
                        "audio_count": audio_count,
                        "total_size_bytes": total_size,
                        "loaded_at": cached_time.isoformat()
                    }
            
            console_logger.info(f"Starting audio preload for user {user_id}, scenario {scenario_id}")
            
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
                return False, f"No voice lines found for scenario {scenario_id}", {"audio_count": 0}
            
            # Verify user owns this scenario
            if voice_lines[0].scenario.user_id != user_id:
                return False, "Unauthorized access to scenario", {"audio_count": 0}
            
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
                return False, "No ready audio files found for preloading", {"audio_count": 0}
            
            console_logger.info(f"Found {len(audio_files_to_load)} audio files to preload")
            
            # Download audio files with concurrency limit
            semaphore = asyncio.Semaphore(self._max_concurrent_downloads)
            preloaded_audio = {}
            
            async def download_single_audio(voice_line: VoiceLine, audio: VoiceLineAudio):
                async with semaphore:
                    audio_data = await self._download_audio_file(audio.storage_path, voice_line.id)
                    if audio_data:
                        preloaded = PreloadedAudio(
                            voice_line_id=voice_line.id,
                            voice_line_type=voice_line.type,
                            order_index=voice_line.order_index,
                            audio_data=audio_data,
                            voice_id=audio.voice_id,
                            duration_ms=audio.duration_ms,
                            size_bytes=len(audio_data),
                            loaded_at=datetime.utcnow(),
                            storage_path=audio.storage_path
                        )
                        # Precompute μ-law chunks for smoother streaming
                        try:
                            chunks_b64, sr, cms = self._precompute_ulaw_chunks(audio_data, chunk_ms=200, sample_rate=8000)
                            preloaded.ulaw_chunks_b64 = chunks_b64
                            preloaded.ulaw_sample_rate_hz = sr
                            preloaded.ulaw_chunk_ms = cms
                        except Exception as _:
                            # Fallback to runtime conversion if precompute fails
                            pass
                        preloaded_audio[voice_line.id] = preloaded
                        console_logger.debug(f"Preloaded voice line {voice_line.id} ({len(audio_data):,} bytes)")
            
            # Execute downloads concurrently
            download_tasks = [
                download_single_audio(voice_line, audio) 
                for voice_line, audio in audio_files_to_load
            ]
            
            await asyncio.gather(*download_tasks, return_exceptions=True)
            
            # Cache the results
            if preloaded_audio:
                self._preload_cache[cache_key] = preloaded_audio
                self._cache_timestamps[cache_key] = datetime.utcnow()
                
                total_size = sum(audio.size_bytes for audio in preloaded_audio.values())
                console_logger.info(f"Successfully preloaded {len(preloaded_audio)} audio files ({total_size:,} bytes) for scenario {scenario_id}")
                
                return True, f"Successfully preloaded {len(preloaded_audio)} audio files", {
                    "cached": False,
                    "audio_count": len(preloaded_audio),
                    "total_size_bytes": total_size,
                    "loaded_at": datetime.utcnow().isoformat(),
                    "voice_lines_by_type": {
                        voice_type.value: len([a for a in preloaded_audio.values() if a.voice_line_type == voice_type])
                        for voice_type in VoiceLineTypeEnum
                    }
                }
            else:
                return False, "Failed to preload any audio files", {"audio_count": 0}
                
        except Exception as e:
            console_logger.error(f"Error preloading audio for scenario {scenario_id}: {str(e)}")
            return False, f"Preload failed: {str(e)}", {"audio_count": 0}
    
    def get_preloaded_audio(self, user_id: str, scenario_id: int, voice_line_id: Optional[int] = None) -> Optional[Dict[int, PreloadedAudio]]:
        """
        Get preloaded audio data from memory
        
        Args:
            user_id: User ID
            scenario_id: Scenario ID  
            voice_line_id: Optional specific voice line ID, if None returns all
            
        Returns:
            Dictionary of voice_line_id -> PreloadedAudio, or None if not preloaded
        """
        cache_key = self._get_cache_key(user_id, scenario_id)
        
        if cache_key not in self._preload_cache:
            return None
        
        # Check if cache is expired
        cached_time = self._cache_timestamps.get(cache_key, datetime.min)
        if datetime.utcnow() - cached_time > timedelta(minutes=self._max_cache_age_minutes):
            console_logger.info(f"Preloaded cache expired for {cache_key}")
            self.drop_preloaded_audio(user_id, scenario_id)
            return None
        
        preloaded_data = self._preload_cache[cache_key]
        
        if voice_line_id is not None:
            if voice_line_id in preloaded_data:
                return {voice_line_id: preloaded_data[voice_line_id]}
            else:
                return None
        
        return preloaded_data.copy()  # Return copy to prevent external modification
    
    def get_audio_by_type(self, user_id: str, scenario_id: int, voice_line_type: VoiceLineTypeEnum) -> List[PreloadedAudio]:
        """
        Get preloaded audio files filtered by voice line type
        
        Args:
            user_id: User ID
            scenario_id: Scenario ID
            voice_line_type: Type of voice line to retrieve
            
        Returns:
            List of PreloadedAudio objects sorted by order_index
        """
        preloaded_data = self.get_preloaded_audio(user_id, scenario_id)
        
        if not preloaded_data:
            return []
        
        filtered_audio = [
            audio for audio in preloaded_data.values() 
            if audio.voice_line_type == voice_line_type
        ]
        
        # Sort by order_index for consistent playback order
        return sorted(filtered_audio, key=lambda x: x.order_index)
    
    def drop_preloaded_audio(self, user_id: str, scenario_id: int) -> bool:
        """
        Remove preloaded audio from memory
        
        Args:
            user_id: User ID
            scenario_id: Scenario ID
            
        Returns:
            True if audio was dropped, False if not found
        """
        cache_key = self._get_cache_key(user_id, scenario_id)
        
        if cache_key in self._preload_cache:
            audio_count = len(self._preload_cache[cache_key])
            total_size = sum(audio.size_bytes for audio in self._preload_cache[cache_key].values())
            
            del self._preload_cache[cache_key]
            if cache_key in self._cache_timestamps:
                del self._cache_timestamps[cache_key]
            
            # Force garbage collection to free memory
            gc.collect()
            
            console_logger.info(f"Dropped preloaded audio for {cache_key} ({audio_count} files, {total_size:,} bytes)")
            return True
        
        return False
    
    @classmethod
    def drop_all_preloaded_audio(cls) -> int:
        """
        Clear all preloaded audio from memory (useful for cleanup/restart)
        
        Returns:
            Number of cache entries dropped
        """
        dropped_count = len(cls._preload_cache)
        
        if dropped_count > 0:
            total_files = sum(len(cache) for cache in cls._preload_cache.values())
            total_size = sum(
                sum(audio.size_bytes for audio in cache.values()) 
                for cache in cls._preload_cache.values()
            )
            
            cls._preload_cache.clear()
            cls._cache_timestamps.clear()
            gc.collect()
            
            console_logger.info(f"Dropped all preloaded audio ({dropped_count} scenarios, {total_files} files, {total_size:,} bytes)")
        
        return dropped_count
    
    def get_preload_stats(self, user_id: Optional[str] = None, scenario_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get statistics about preloaded audio
        
        Args:
            user_id: Optional user ID filter
            scenario_id: Optional scenario ID filter (requires user_id)
            
        Returns:
            Dictionary with preload statistics
        """
        if user_id and scenario_id:
            # Stats for specific user-scenario
            cache_key = self._get_cache_key(user_id, scenario_id)
            if cache_key in self._preload_cache:
                preloaded_data = self._preload_cache[cache_key]
                loaded_at = self._cache_timestamps.get(cache_key)
                total_size = sum(audio.size_bytes for audio in preloaded_data.values())
                
                return {
                    "cache_key": cache_key,
                    "audio_count": len(preloaded_data),
                    "total_size_bytes": total_size,
                    "loaded_at": loaded_at.isoformat() if loaded_at else None,
                    "voice_lines_by_type": {
                        voice_type.value: len([a for a in preloaded_data.values() if a.voice_line_type == voice_type])
                        for voice_type in VoiceLineTypeEnum
                    }
                }
            else:
                return {"cache_key": cache_key, "audio_count": 0, "total_size_bytes": 0}
        
        # Global stats
        total_scenarios = len(self._preload_cache)
        total_files = sum(len(cache) for cache in self._preload_cache.values())
        total_size = sum(
            sum(audio.size_bytes for audio in cache.values()) 
            for cache in self._preload_cache.values()
        )
        
        return {
            "total_scenarios": total_scenarios,
            "total_files": total_files,
            "total_size_bytes": total_size,
            "cache_keys": list(self._preload_cache.keys()),
            "max_cache_age_minutes": self._max_cache_age_minutes
        }