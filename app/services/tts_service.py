# app/services/tts_service.py
from elevenlabs import Voice, VoiceSettings
from elevenlabs.client import ElevenLabs
from supabase import create_client, Client
from app.core.config import settings
from app.core.logging import console_logger
import uuid
from typing import Optional, Tuple
from datetime import datetime, timezone
from app.core.utils.enums import ElevenLabsModelEnum, ElevenLabsVoiceIdEnum, LanguageEnum, GenderEnum, get_voice_id

class TTSService: 
    """Unified TTS generation and storage service with user-dependent private storage"""

    def __init__(self):
        # ElevenLabs client
        self.client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
        
        # Supabase client for storage
        self.storage_client: Client = create_client(
            settings.SUPABASE_URL, 
            settings.SUPABASE_SERVICE_ROLE_KEY
        )
        self.bucket_name = "voice-lines"

    async def generate_audio(self, text: str, voice_id: str = None, 
                           language: LanguageEnum = None, gender: GenderEnum = None,
                           model: ElevenLabsModelEnum = ElevenLabsModelEnum.ELEVEN_TTV_V3) -> bytes:
        """
        Generate audio from text using ElevenLabs TTS
        
        Args:
            text: Text to convert to speech
            voice_id: Specific voice ID (overrides language/gender selection)
            language: Language for voice selection
            gender: Gender for voice selection  
            model: ElevenLabs model to use (default: Eleven v3)
        """
        try:
            # Determine voice ID
            if voice_id:
                selected_voice_id = voice_id
            elif language and gender:
                selected_voice_id = get_voice_id(language, gender)
            else:
                selected_voice_id = ElevenLabsVoiceIdEnum.GERMAN_MALE_FELIX.value 
            
            console_logger.info(f"Generating audio with voice {selected_voice_id}, model {model.value}")
            console_logger.info(f"Text: {text[:50]}...")
            
            audio_generator = self.client.text_to_speech.convert(
                text=text,
                voice_id=selected_voice_id,
                voice_settings=VoiceSettings(
                    stability=0.50,        
                    similarity_boost=0.75,  
                    style=0.0,
                    speed=1.0,
                    use_speaker_boost=True 
                ),
                model_id=model.value
            )
            
            # Convert generator to bytes
            audio_bytes = b''.join(audio_generator)
            
            console_logger.info("Audio generation successful")
            return audio_bytes
            
        except Exception as e:
            console_logger.error(f"TTS generation failed: {str(e)}")
            raise

    def _get_storage_path(self, user_id: str, voice_line_id: int) -> str:
        """
        Generate private storage path for user
        Structure: /private/{user_id}/voice_lines/{voice_line_id}_{timestamp}_{uuid}.mp3
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{voice_line_id}_{timestamp}_{uuid.uuid4().hex[:8]}.mp3"
        return f"private/{user_id}/voice_lines/{filename}"

    async def store_audio_file(self, audio_data: bytes, voice_line_id: int, user_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Store audio file in Supabase Storage with user-dependent private path
        
        Returns:
            Tuple[signed_url: Optional[str], storage_path: Optional[str]]
        """
        try:
            # Generate user-dependent private path
            file_path = self._get_storage_path(user_id, voice_line_id)
            
            console_logger.info(f"Storing private audio file: {file_path}")
            console_logger.info(f"Audio data size: {len(audio_data)} bytes")
            
            # Upload to Supabase Storage
            response = self.storage_client.storage.from_(self.bucket_name).upload(
                path=file_path,
                file=audio_data,
                file_options={
                    "content-type": "audio/mpeg",
                    "cache-control": "3600",
                    "upsert": "false"
                }
            )
            
            # Modern Supabase client doesn't have .error attribute
            # Instead, check if upload was successful by examining the response
            console_logger.info(f"Upload successful, response: {response}")
            
            # Generate signed URL for private access (valid for 1 hour)
            signed_url_response = self.storage_client.storage.from_(self.bucket_name).create_signed_url(
                path=file_path,
                expires_in=3600  # 1 hour
            )
            
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
            
            console_logger.info(f"Private audio stored successfully with signed URL")
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
            signed_url_response = self.storage_client.storage.from_(self.bucket_name).create_signed_url(
                path=storage_path,
                expires_in=expires_in
            )
            
            # Handle different response formats
            if hasattr(signed_url_response, 'data') and signed_url_response.data:
                return signed_url_response.data.get('signedURL')
            elif isinstance(signed_url_response, dict):
                return signed_url_response.get('signedURL')
            else:
                return signed_url_response
                
        except Exception as e:
            console_logger.error(f"Error getting audio URL: {str(e)}")
            return None

    async def generate_and_store_audio(self, text: str, voice_line_id: int, user_id: str,
                                     voice_id: str = None, language: LanguageEnum = None, 
                                     gender: GenderEnum = None,
                                     model: ElevenLabsModelEnum = ElevenLabsModelEnum.ELEVEN_TTV_V3) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Generate TTS audio and store it in one operation
        
        Returns:
            Tuple[success: bool, signed_url: Optional[str], storage_path: Optional[str], error_message: Optional[str]]
        """
        try:
            console_logger.info(f"Generating and storing audio for voice line {voice_line_id} (user: {user_id})")
            
            # Step 1: Generate audio with voice selection
            audio_data = await self.generate_audio(text, voice_id, language, gender, model)
            
            # Step 2: Store audio with user-dependent path
            signed_url, storage_path = await self.store_audio_file(audio_data, voice_line_id, user_id)
            
            if signed_url and storage_path:
                console_logger.info(f"Voice line {voice_line_id} successfully generated and stored")
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
            console_logger.info(f"Deleting audio file: {storage_path}")
            
            response = self.storage_client.storage.from_(self.bucket_name).remove([storage_path])
            
            # Modern Supabase client doesn't have .error attribute
            # If no exception is raised, consider it successful
            console_logger.info(f"Audio file deleted successfully: {storage_path}")
            return True
            
        except Exception as e:
            console_logger.error(f"Storage delete error: {str(e)}")
            return False

    async def regenerate_audio(self, old_storage_path: str, new_text: str, voice_line_id: int, 
                             user_id: str, voice_id: str = None, language: LanguageEnum = None, 
                             gender: GenderEnum = None,
                             model: ElevenLabsModelEnum = ElevenLabsModelEnum.ELEVEN_TTV_V3) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Regenerate audio (delete old, create new) with user-dependent storage
        
        Returns:
            Tuple[success: bool, new_signed_url: Optional[str], new_storage_path: Optional[str], error_message: Optional[str]]
        """
        try:
            console_logger.info(f"Regenerating audio for voice line {voice_line_id}")
            
            # Generate new audio first
            success, new_signed_url, new_storage_path, error_msg = await self.generate_and_store_audio(
                new_text, voice_line_id, user_id, voice_id, language, gender, model
            )
            
            if success and new_signed_url:
                # Delete old audio file (don't fail if this doesn't work)
                if old_storage_path:
                    delete_success = await self.delete_audio_file(old_storage_path)
                    if not delete_success:
                        console_logger.warning(f"Failed to delete old audio file: {old_storage_path}")
                
                console_logger.info(f"Audio regeneration successful for voice line {voice_line_id}")
                return True, new_signed_url, new_storage_path, None
            else:
                return False, None, None, error_msg
                
        except Exception as e:
            error_msg = f"Audio regeneration failed: {str(e)}"
            console_logger.error(error_msg)
            return False, None, None, error_msg