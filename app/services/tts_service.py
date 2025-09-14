# app/services/tts_service.py
from elevenlabs import Voice, VoiceSettings
from elevenlabs.client import ElevenLabs
from supabase import create_client, Client
from app.core.config import settings
from app.core.logging import console_logger
import uuid
from typing import Optional, Tuple, Dict, List
from datetime import datetime, timezone
from app.core.utils.enums import ElevenLabsModelEnum, ElevenLabsVoiceIdEnum, LanguageEnum, GenderEnum
from app.core.utils.voices_catalog import get_voice_id, DEFAULT_SETTINGS
import hashlib
import json
import re
import asyncio
 
import os
import random
from app.services.cache_service import CacheService
from app.core.utils.audio import pcm16_to_wav_with_tempo
from app.core.utils.tts_common import (
    compute_text_hash as compute_text_hash_fn,
    compute_settings_hash as compute_settings_hash_fn,
    compute_content_hash as compute_content_hash_fn,
    private_voice_line_storage_path,
)


TTS_ATTEMPT_TIMEOUT = int(os.getenv("TTS_ATTEMPT_TIMEOUT", "20"))
TTS_OVERALL_TIMEOUT = int(os.getenv("TTS_OVERALL_TIMEOUT", "120"))
SUPABASE_TIMEOUT = int(os.getenv("SUPABASE_TIMEOUT", "20"))


class TTSService: 
    """Unified TTS generation and storage service with user-dependent private storage"""

    # Process-wide concurrency gate for ElevenLabs TTS (simple in-process queue)
    # Tune via ELEVENLABS_MAX_CONCURRENCY env var; defaults to 2 (e.g., Free plan)
    _MAX_CONCURRENCY = int(os.getenv("ELEVENLABS_MAX_CONCURRENCY", "2"))
    _SEM = asyncio.Semaphore(_MAX_CONCURRENCY)

    def __init__(self):
        # ElevenLabs client
        self.client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
        
        # Supabase client for storage
        self.storage_client: Client = create_client(
            settings.SUPABASE_URL, 
            settings.SUPABASE_SERVICE_ROLE_KEY
        )
        self.bucket_name = "voice-lines"

    def select_voice_id(self, voice_id: Optional[str]) -> str:
        """Voice-Auswahl optimiert für Youth-Appeal und Akzent-Fähigkeiten"""
        if voice_id:
            return voice_id
        # Default zu expressiveren Stimmen für junge Zielgruppe
        return ElevenLabsVoiceIdEnum.GERMAN_MALE_FELIX.value

    def default_voice_settings(self) -> Dict:
        """Optimierte Einstellungen für ElevenLabs v3 mit Audio-Tags und Akzenten"""
        return DEFAULT_SETTINGS

    def _normalize_text(self, text: str) -> str:
        t = text.strip()
        return t


    def compute_text_hash(self, text: str) -> str:
        return compute_text_hash_fn(text)

    def compute_settings_hash(self, voice_id: str, model_id: ElevenLabsModelEnum, voice_settings: Optional[Dict]) -> str:
        return compute_settings_hash_fn(
            voice_id,
            model_id.value if isinstance(model_id, ElevenLabsModelEnum) else model_id,
            voice_settings or self.default_voice_settings(),
        )

    def compute_content_hash(self, text: str, voice_id: str, model_id: ElevenLabsModelEnum, voice_settings: Optional[Dict]) -> str:
        return compute_content_hash_fn(
            text,
            voice_id,
            model_id.value if isinstance(model_id, ElevenLabsModelEnum) else model_id,
            voice_settings or self.default_voice_settings(),
        )
    

    def _pcm16_to_wav(self, pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1, tempo: Optional[float] = None) -> bytes:
        # Use shared utility to convert PCM to WAV and apply pitch-preserving tempo (defaults via env in utility)
        return pcm16_to_wav_with_tempo(pcm_bytes, sample_rate=sample_rate, channels=channels, tempo=tempo)

    
    
    async def generate_audio(self, text: str, voice_id: str = None, 
                           model: ElevenLabsModelEnum = ElevenLabsModelEnum.ELEVEN_TTV_V3,
                           voice_settings: Optional[Dict] = None) -> bytes:
        """
        Generate audio from text using ElevenLabs TTS
        
        Args:
            text: Text to convert to speech
            voice_id: Specific voice ID
            language: Language for voice selection
            gender: Gender for voice selection  
            model: ElevenLabs model to use (default: Eleven v3)
        """
        try:
            # Determine voice ID
            selected_voice_id = self.select_voice_id(voice_id)

            vs_dict = voice_settings or self.default_voice_settings()

            def _convert_sync() -> bytes:
                # ElevenLabs SDK is synchronous; run in a thread to avoid blocking the event loop
                generator = self.client.text_to_speech.convert(
                    text=text,
                    voice_id=selected_voice_id,
                    voice_settings=VoiceSettings(**vs_dict),
                    model_id=model.value,
                    output_format="pcm_16000"
                )
                return b"".join(generator)

            # Exponential backoff on rate limiting; queue via process-wide semaphore
            max_attempts = 6
            base_delay = 1.0  # seconds
            deadline = asyncio.get_running_loop().time() + TTS_OVERALL_TIMEOUT
            async with self._SEM:
                for attempt in range(1, max_attempts + 1):
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise asyncio.TimeoutError("TTS overall deadline exceeded")
                    attempt_timeout = min(TTS_ATTEMPT_TIMEOUT, max(0.1, remaining))
                    console_logger.info(f"Attempt {attempt}/{max_attempts} (timeout {attempt_timeout}s) to generate audio")
                    try:
                        audio_bytes = await asyncio.wait_for(asyncio.to_thread(_convert_sync), timeout=attempt_timeout)
                        console_logger.debug("Audio generation successful")
                        return audio_bytes
                    except asyncio.TimeoutError:
                        if attempt < max_attempts:
                            delay = min(10.0, base_delay * (2 ** (attempt - 1)))
                            console_logger.warning(
                                f"ElevenLabs attempt {attempt} timed out after {attempt_timeout}s; retrying in {delay:.2f}s"
                            )
                            await asyncio.sleep(delay)
                            continue
                        console_logger.error("ElevenLabs TTS timed out on final attempt")
                        raise
                    except Exception as e:
                        msg = str(e).lower()
                        is_rate_limited = (
                            "429" in msg
                            or "too_many_concurrent_requests" in msg
                            or "system_busy" in msg
                            or "rate limit" in msg
                        )
                        # Treat common transient/server issues as retryable
                        transient_tokens = [
                            "upstream connect error",
                            "disconnect/reset",
                            "connection termination",
                            "connection reset",
                            "reset reason",
                            "econnreset",
                            "temporarily unavailable",
                            "timeout",
                            "timed out",
                            "bad gateway",
                            "service unavailable",
                            "gateway timeout",
                            "server error",
                            "connect error",
                        ]
                        is_5xx = bool(re.search(r"\b5\d{2}\b", msg)) or any(code in msg for code in [" 502", " 503", " 504"]) 
                        is_transient = is_rate_limited or is_5xx or any(t in msg for t in transient_tokens)

                        if is_transient and attempt < max_attempts:
                            delay = min(10.0, base_delay * (2 ** (attempt - 1)))
                            reason = "rate-limited/busy" if is_rate_limited else "transient 5xx/network issue"
                            console_logger.warning(
                                f"ElevenLabs {reason} (attempt {attempt}/{max_attempts}); retrying in {delay:.2f}s"
                            )
                            await asyncio.sleep(delay)
                            continue
                        console_logger.error(f"TTS generation failed on attempt {attempt}: {str(e)}")
                        console_logger.error(f"Failed text: {text[:100]}...")
                        console_logger.error(f"Voice ID: {selected_voice_id}, Model: {model.value}")
                        raise


        except Exception:
            # Already logged above; re-raise to caller
            raise

    def _get_storage_path(self, user_id: str, voice_line_id: int) -> str:
        """Generate private storage path for user."""
        return private_voice_line_storage_path(user_id, voice_line_id)

    async def store_audio_file(self, audio_data: bytes, voice_line_id: int, user_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Store audio file in Supabase Storage with user-dependent private path
        
        Returns:
            Tuple[signed_url: Optional[str], storage_path: Optional[str]]
        """
        try:
            # Generate user-dependent private path
            file_path = self._get_storage_path(user_id, voice_line_id)
            
            console_logger.debug(f"Storing private audio file: {file_path}")
            console_logger.debug(f"Audio data size: {len(audio_data)} bytes")
            
            # Upload to Supabase Storage (blocking client) in a thread
            def _upload_sync():
                return self.storage_client.storage.from_(self.bucket_name).upload(
                    path=file_path,
                    file=audio_data,
                    file_options={
                        "content-type": "audio/wav",
                        "cache-control": "3600",
                        "upsert": "false"
                    }
                )

            # Retry public storage upload on transient network/server errors
            max_attempts = 6
            base_delay = 0.5
            response = None
            for attempt in range(1, max_attempts + 1):
                try:
                    response = await asyncio.wait_for(asyncio.to_thread(_upload_sync), timeout=SUPABASE_TIMEOUT)
                    break
                except Exception as e:
                    msg = str(e).lower()
                    transient_tokens = [
                        "timeout",
                        "timed out",
                        "read operation timed out",
                        "connection reset",
                        "econnreset",
                        "upstream connect error",
                        "bad gateway",
                        "service unavailable",
                        "gateway timeout",
                        "temporarily unavailable",
                        "connect error",
                    ]
                    is_5xx = bool(re.search(r"\b5\d{2}\b", msg)) or any(code in msg for code in [" 502", " 503", " 504"]) 
                    is_transient = is_5xx or any(t in msg for t in transient_tokens)
                    if is_transient and attempt < max_attempts:
                        delay = min(10.0, base_delay * (2 ** (attempt - 1))) + random.random() * 0.25
                        console_logger.warning(
                            f"Supabase storage upload transient failure (attempt {attempt}/{max_attempts}); retrying in {delay:.2f}s"
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise
            
            # Modern Supabase client doesn't have .error attribute
            # Instead, check if upload was successful by examining the response
            console_logger.debug(f"Upload successful, response: {response}")
            
            # Generate signed URL for private access (valid for 1 hour)
            def _signed_url_sync():
                return self.storage_client.storage.from_(self.bucket_name).create_signed_url(
                    path=file_path,
                    expires_in=3600  # 1 hour
                )

            signed_url_response = await asyncio.wait_for(asyncio.to_thread(_signed_url_sync), timeout=SUPABASE_TIMEOUT)
            
            # Extract signed URL from response
            if hasattr(signed_url_response, 'data') and signed_url_response.data:
                signed_url = signed_url_response.data.get('signedURL')
            elif isinstance(signed_url_response, dict):
                signed_url = signed_url_response.get('signedURL')
            else:
                signed_url = signed_url_response
            
            if not signed_url:
                console_logger.error(f"Failed to create signed URL: {signed_url_response}")
                return None, None
            
            console_logger.debug(f"Private audio stored successfully with signed URL")
            return signed_url, file_path
            
        except Exception as e:
            console_logger.error(f"Storage upload error: {str(e)}")
            console_logger.error(f"Error type: {type(e).__name__}")
            import traceback
            console_logger.error(f"Traceback: {traceback.format_exc()}")
            return None, None

    async def get_audio_url(self, storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """
        Get signed URL for accessing private audio file
        
        Args:
            storage_path: The storage path of the file
            expires_in: Expiration time for signed URLs (seconds, default 1 hour)
        """
        try:
            def _signed_url_sync():
                return self.storage_client.storage.from_(self.bucket_name).create_signed_url(
                    path=storage_path,
                    expires_in=expires_in
                )

            max_attempts = 6
            base_delay = 0.5
            for attempt in range(1, max_attempts + 1):
                try:
                    signed_url_response = await asyncio.wait_for(asyncio.to_thread(_signed_url_sync), timeout=SUPABASE_TIMEOUT)
                    # Handle different response formats
                    if hasattr(signed_url_response, 'data') and signed_url_response.data:
                        return signed_url_response.data.get('signedURL')
                    elif isinstance(signed_url_response, dict):
                        return signed_url_response.get('signedURL')
                    else:
                        return signed_url_response
                except Exception as e:
                    msg = str(e).lower()
                    transient_tokens = [
                        "timeout",
                        "timed out",
                        "read operation timed out",
                        "connection reset",
                        "econnreset",
                        "upstream connect error",
                        "bad gateway",
                        "service unavailable",
                        "gateway timeout",
                        "temporarily unavailable",
                        "connect error",
                    ]
                    is_5xx = bool(re.search(r"\b5\d{2}\b", msg)) or any(code in msg for code in [" 502", " 503", " 504"]) 
                    is_transient = is_5xx or any(t in msg for t in transient_tokens)
                    if is_transient and attempt < max_attempts:
                        delay = min(10.0, base_delay * (2 ** (attempt - 1))) + random.random() * 0.25
                        console_logger.warning(
                            f"Signed URL generation transient failure (attempt {attempt}/{max_attempts}); retrying in {delay:.2f}s"
                        )
                        await asyncio.sleep(delay)
                        continue
                    console_logger.error(f"Error getting audio URL: {str(e)}")
                    return None
        except Exception as e:
            console_logger.error(f"Error getting audio URL: {str(e)}")
            return None

    async def get_audio_urls_batch(self, storage_paths: List[str], expires_in: int = 3600) -> Dict[str, Optional[str]]:
        """
        Create signed URLs in bulk using Supabase's Python API and cache results in Redis.
        Docs: https://supabase.com/docs/reference/python/storage-from-createsignedurls
        """
        if not storage_paths:
            return {}

        cache = await CacheService.get_global()
        cache_prefix = "tts:signed"

        results: Dict[str, Optional[str]] = {}
        missing: List[str] = []
        for path in storage_paths:
            try:
                cached = await cache.get(path, prefix=cache_prefix)
            except Exception:
                cached = None
            if cached:
                results[path] = cached
            else:
                missing.append(path)

        if missing:
            def _batch_sign_sync():
                return (
                    self.storage_client
                    .storage
                    .from_(self.bucket_name)
                    .create_signed_urls(missing, expires_in)
                )

            # Retry on transient failures
            max_attempts = 5
            base_delay = 0.5
            response = None
            for attempt in range(1, max_attempts + 1):
                try:
                    response = await asyncio.wait_for(asyncio.to_thread(_batch_sign_sync), timeout=SUPABASE_TIMEOUT)
                    break
                except Exception as e:
                    msg = str(e).lower()
                    transient_tokens = [
                        "timeout",
                        "timed out",
                        "read operation timed out",
                        "connection reset",
                        "econnreset",
                        "upstream connect error",
                        "bad gateway",
                        "service unavailable",
                        "gateway timeout",
                        "temporarily unavailable",
                        "connect error",
                    ]
                    is_5xx = bool(re.search(r"\b5\d{2}\b", msg)) or any(code in msg for code in [" 502", " 503", " 504"]) 
                    is_transient = is_5xx or any(t in msg for t in transient_tokens)
                    if is_transient and attempt < max_attempts:
                        delay = min(10.0, base_delay * (2 ** (attempt - 1))) + random.random() * 0.25
                        console_logger.warning(
                            f"Batch signed URL generation transient failure (attempt {attempt}/{max_attempts}); retrying in {delay:.2f}s"
                        )
                        await asyncio.sleep(delay)
                        continue
                    console_logger.error(f"Batch signed URL generation failed: {str(e)}")
                    break
            # Normalize response to a list of item dicts
            if hasattr(response, "data"):
                items = response.data
            elif isinstance(response, dict):
                items = response.get("data", [])
            elif isinstance(response, list):
                items = response
            else:
                items = []
            for idx, path in enumerate(missing):
                signed_url = None
                if idx < len(items) and isinstance(items[idx], dict):
                    signed_url = items[idx].get("signedURL")
                results[path] = signed_url
                if signed_url:
                    # Cache slightly shorter than expiry to reduce stale entries
                    ttl = max(60, expires_in - 60)
                    try:
                        await cache.set(path, signed_url, ttl=ttl, prefix=cache_prefix)
                    except Exception:
                        pass

        return results

    async def generate_and_store_audio(self, text: str, voice_line_id: int, user_id: str,
                                     voice_id: str = None, model: ElevenLabsModelEnum = ElevenLabsModelEnum.ELEVEN_TTV_V3,
                                     voice_settings: Optional[Dict] = None) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Generate TTS audio and store it in one operation
        
        Returns:
            Tuple[success: bool, signed_url: Optional[str], storage_path: Optional[str], error_message: Optional[str]]
        """
        try:
            console_logger.debug(f"Generating and storing audio for voice line {voice_line_id} (user: {user_id})")
            
            # Step 1: Generate audio with voice selection (overall guard)
            overall_timeout = max(10, TTS_OVERALL_TIMEOUT + 15)
            audio_data = await asyncio.wait_for(
                self.generate_audio(text, voice_id, model, voice_settings),
                timeout=overall_timeout
            )
            wav_bytes = self._pcm16_to_wav(audio_data)
            
            # Step 2: Store audio with user-dependent path
            signed_url, storage_path = await self.store_audio_file(wav_bytes, voice_line_id, user_id)
            
            if signed_url and storage_path:
                console_logger.debug(f"Voice line {voice_line_id} successfully generated and stored")
                return True, signed_url, storage_path, None
            else:
                error_msg = "Audio generation succeeded but storage failed"
                console_logger.error(error_msg)
                return False, None, None, error_msg
                
        except Exception as e:
            error_msg = f"TTS generation and storage failed: {str(e)}"
            console_logger.error(error_msg)
            return False, None, None, error_msg

    async def delete_audio_file(self, storage_path: str) -> bool:
        """Delete audio file from Supabase Storage using storage path"""
        try:
            console_logger.debug(f"Deleting audio file: {storage_path}")
            
            def _remove_sync():
                return self.storage_client.storage.from_(self.bucket_name).remove([storage_path])

            _ = await asyncio.to_thread(_remove_sync)
            
            # Modern Supabase client doesn't have .error attribute
            # If no exception is raised, consider it successful
            console_logger.debug(f"Audio file deleted successfully: {storage_path}")
            return True
            
        except Exception as e:
            console_logger.error(f"Storage delete error: {str(e)}")
            return False

    async def regenerate_audio(self, old_storage_path: str, new_text: str, voice_line_id: int, 
                             user_id: str, voice_id: str = None, 
                             model: ElevenLabsModelEnum = ElevenLabsModelEnum.ELEVEN_TTV_V3,
                             voice_settings: Optional[Dict] = None) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Regenerate audio (delete old, create new) with user-dependent storage
        
        Returns:
            Tuple[success: bool, new_signed_url: Optional[str], new_storage_path: Optional[str], error_message: Optional[str]]
        """
        try:
            console_logger.debug(f"Regenerating audio for voice line {voice_line_id}")
            
            # Generate new audio first
            success, new_signed_url, new_storage_path, error_msg = await self.generate_and_store_audio(
                new_text, voice_line_id, user_id, voice_id, model, voice_settings
            )
            
            if success and new_signed_url:
                # Delete old audio file (don't fail if this doesn't work)
                if old_storage_path:
                    delete_success = await self.delete_audio_file(old_storage_path)
                    if not delete_success:
                        console_logger.warning(f"Failed to delete old audio file: {old_storage_path}")
                
                console_logger.debug(f"Audio regeneration successful for voice line {voice_line_id}")
                return True, new_signed_url, new_storage_path, None
            else:
                return False, None, None, error_msg
                
        except Exception as e:
            error_msg = f"Audio regeneration failed: {str(e)}"
            console_logger.error(error_msg)
            return False, None, None, error_msg