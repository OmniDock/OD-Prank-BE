from typing import List, Optional, Dict, Any
from supabase import create_client, Client
from app.core.config import settings
from app.core.logging import console_logger
from app.core.utils.enums import ElevenLabsModelEnum
from app.services.tts_service import TTSService
from app.core.utils.voices_catalog import PREVIEW_VERSION


class PreviewTTSService:
    """Service to ensure short public preview clips exist for each voice_id.

    Previews are stored in the same bucket as private assets but under a public path:
      voice-lines/public/voice-previews/{voice_id}.mp3

    The resulting public URL is:
      {SUPABASE_URL}/storage/v1/object/public/voice-lines/public/voice-previews/{voice_id}.mp3
    """

    def __init__(self) -> None:
        self.bucket_name = "voice-lines"
        self.public_prefix = f"public/voice-previews/{PREVIEW_VERSION}"
        
        # Longer, expressive prank-call style previews with textual cues (eleven_v3)
        self.preview_text_default_en = (
            "[loudly] Good evening! [coughing] Tiny emergency… [normal] "
            "[confident] Quick check: What has two thumbs and makes bad jokes? "
            "[sarcastic] Not me, guy? [laughs softly] [long pause]  "
            "[annoyed] Jokes aside — Ready when you are!"
        )
        self.preview_text_default_de = (
            "[loudly] Ijooo! [coughing] Mini-Notfall… [normal] "
            "[confident] Kurzer Test: Was hat zwei Daumen und vermasselt ständig Witze? "
            "[sarcastic] Ich nicht? [laughs softly] [long pause]  "
            "[annoyed] Spaß beiseite –. Bereit, wenn du’s bist!"
        )

        # Storage and TTS
        self.storage_client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
        self.tts_service = TTSService()

    def _public_url(self, path: str) -> str:
        # Note: path should not start with leading slash
        return f"{settings.SUPABASE_URL}/storage/v1/object/public/{self.bucket_name}/{path}"

    def _object_exists(self, path: str) -> bool:
        try:
            # List the directory and check for the file name
            # Example: path = "public/voice-previews/VOICEID.mp3"
            directory, file_name = path.rsplit("/", 1)
            items = self.storage_client.storage.from_(self.bucket_name).list(directory)
            for item in items or []:
                # Supabase client may return dicts or objects; handle both
                name = getattr(item, "name", None) if not isinstance(item, dict) else item.get("name")
                if name == file_name:
                    return True
            return False
        except Exception as e:
            console_logger.warning(f"Failed to check existence for {path}: {e}")
            return False

    def preview_voice_settings(self) -> Dict[str, Any]:
        """More expressive defaults for previews with eleven_v3."""
        return {
            "stability": 0.5,            
            "similarity_boost": 0.75,    
            "style": 0.0,                
            "speed": 1.02,               
            "use_speaker_boost": True,
        }

    async def _generate_preview_bytes(self, voice_id: str, preview_text: Optional[str] = None) -> bytes:
        text = preview_text or self.preview_text_default_en
        # Always use v3 as agreed
        model = ElevenLabsModelEnum.ELEVEN_TTV_V3
        # Use expressive preview voice settings
        vs = self.preview_voice_settings()
        audio_bytes = await self.tts_service.generate_audio(
            text=text,
            voice_id=voice_id,
            language=None,
            gender=None,
            model=model,
            voice_settings=vs,
        )
        return audio_bytes

    def _upload_public(self, path: str, data: bytes) -> bool:
        try:
            res = self.storage_client.storage.from_(self.bucket_name).upload(
                path=path,
                file=data,
                file_options={
                    "content-type": "audio/mpeg",
                    "cache-control": "2592000",  # 30 days
                    "upsert": "false",
                },
            )
            console_logger.info(f"Uploaded preview to {path}: {res}")
            return True
        except Exception as e:
            console_logger.error(f"Failed to upload preview {path}: {e}")
            return False

    async def ensure_previews(self, voice_ids: List[str], preview_text: Optional[str] = None) -> None:
        """Ensure a preview file exists for every given voice_id.

        Idempotent: existing files are not overwritten (upsert=false).
        """
        for vid in voice_ids:
            try:
                path = f"{self.public_prefix}/{vid}.mp3"
                if self._object_exists(path):
                    continue
                console_logger.info(f"Generating preview for voice {vid}")
                audio_bytes = await self._generate_preview_bytes(vid, preview_text)
                ok = self._upload_public(path, audio_bytes)
                if not ok:
                    console_logger.warning(f"Upload failed for preview {vid}")
            except Exception as e:
                console_logger.error(f"Error ensuring preview for {vid}: {e}")

    def build_preview_url(self, voice_id: str) -> str:
        path = f"{self.public_prefix}/{voice_id}.mp3"
        return self._public_url(path)

    def _preview_text_for_language(self, primary_language) -> str:
        try:
            from app.core.utils.enums import LanguageEnum
            if primary_language == LanguageEnum.GERMAN:
                return self.preview_text_default_de
            # Default English for unknowns/others
            return self.preview_text_default_en
        except Exception:
            return self.preview_text_default_en

    async def ensure_previews_for_catalog(self, voices_catalog: List[Dict[str, Any]]) -> None:
        """Ensure previews using primary language (first in languages list) per voice.

        voices_catalog items must contain: id (str), languages (List[LanguageEnum]).
        """
        for item in voices_catalog:
            vid = item.get("id")
            langs = item.get("languages") or []
            primary_lang = langs[0] if langs else None
            text = self._preview_text_for_language(primary_lang)
            try:
                path = f"{self.public_prefix}/{vid}.mp3"
                if self._object_exists(path):
                    continue
                console_logger.info(f"Generating preview for voice {vid} (lang: {primary_lang})")
                audio_bytes = await self._generate_preview_bytes(vid, text)
                ok = self._upload_public(path, audio_bytes)
                if not ok:
                    console_logger.warning(f"Upload failed for preview {vid}")
            except Exception as e:
                console_logger.error(f"Error ensuring preview for {vid}: {e}")


