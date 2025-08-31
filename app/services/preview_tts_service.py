from typing import List, Optional, Dict, Any
from app.core.config import settings
from app.core.logging import console_logger
from app.core.utils.enums import ElevenLabsModelEnum, LanguageEnum, GenderEnum
from app.services.tts_service import TTSService
from app.core.utils.voices_catalog import PREVIEW_VERSION, get_voices_catalog
import io
import wave


class PreviewTTSService:
    """Service to ensure short public preview clips exist for each voice_id.

    Previews are stored in the same bucket as private assets but under a public path:
      voice-lines/public/voice-previews/{voice_id}.wav

    The resulting public URL is:
      {SUPABASE_URL}/storage/v1/object/public/voice-lines/public/voice-previews/{voice_id}.wav
    """

    def __init__(self) -> None:
        # Reuse TTSService client and storage
        self.tts_service = TTSService()
        self.bucket_name = self.tts_service.bucket_name
        self.public_prefix = f"public/voice-previews/{PREVIEW_VERSION}"
        
        # Longer preview texts; language + gender variants
        # EN male
        self.preview_text_en_male = (
            "[exhales] Hey there! Giuseppe from WiFi Support. [confused] Your internet is... "
            "acting really weird right now. [whispers] Quick question though... "
            "[curious] do you guys like pineapple pizza? [slight accent] Mama mia, "
            "[laughs] that's important for the... uh... connection quality!"
        )
        # EN female
        self.preview_text_en_female = (
            "[exhales] Hey there! Valentina from WiFi Support. [confused] Your internet is... "
            "acting really weird right now. [whispers] Quick question though... "
            "[curious] do you guys like pineapple pizza? [slight accent] Mama mia, "
            "[laughs] that's important for the... uh... connection quality!"
        )
        # DE male
        self.preview_text_de_male = (
            "[sighs] Hallo! Giuseppe hier von der Technik. [confused] Ihr Internet macht "
            "gerade echt komische Sachen. [whispers] Aber mal ehrlich... "
            "[curious] mögt ihr eigentlich Ananas-Pizza? [slight accent] Madonna mia, "
            "[laughs] das ist wichtig für die... äh... Verbindungsqualität!"
        )
        # DE female
        self.preview_text_de_female = (
            "[sighs] Hallo! Valentina hier von der Technik. [confused] Ihr Internet macht "
            "gerade echt komische Sachen. [whispers] Aber mal ehrlich... "
            "[curious] mögt ihr eigentlich Ananas-Pizza? [slight accent] Madonna mia, "
            "[laughs] das ist wichtig für die... äh... Verbindungsqualität!"
        )

        # Storage is reused from TTSService

    def _pcm16_to_wav(self, pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    def _public_url(self, path: str) -> str:
        # Note: path should not start with leading slash
        return f"{settings.SUPABASE_URL}/storage/v1/object/public/{self.bucket_name}/{path}"

    def _object_exists(self, path: str) -> bool:
        try:
            # List the directory and check for the file name
            # Example: path = "public/voice-previews/VOICEID.wav"
            directory, file_name = path.rsplit("/", 1)
            items = self.tts_service.storage_client.storage.from_(self.bucket_name).list(directory)
            for item in items or []:
                # Supabase client may return dicts or objects; handle both
                name = getattr(item, "name", None) if not isinstance(item, dict) else item.get("name")
                if name == file_name:
                    return True
            return False
        except Exception as e:
            console_logger.warning(f"Failed to check existence for {path}: {e}")
            return False

    def _validate_language_and_gender(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """Ensure the catalog entry exists and includes language and gender."""
        catalog = get_voices_catalog()
        item = next((v for v in catalog if v.get("id") == voice_id), None)
        if not item:
            console_logger.warning(f"Preview skipped: voice {voice_id} not in catalog")
            return None
        langs = item.get("languages") or []
        gender = item.get("gender")
        if not langs or not isinstance(langs[0], LanguageEnum):
            console_logger.warning(f"Preview skipped: missing/invalid language for voice {voice_id}")
            return None
        if gender not in (GenderEnum.MALE, GenderEnum.FEMALE):
            console_logger.warning(f"Preview skipped: missing/invalid gender for voice {voice_id}")
            return None
        return item

    async def _generate_preview_bytes(self, voice_id: str, preview_text: Optional[str] = None) -> bytes:
        text = preview_text or self.preview_text_default_en
        # Always use v3
        model = ElevenLabsModelEnum.ELEVEN_TTV_V3
        # Reuse standard service settings to keep one ElevenLabs config
        vs = self.tts_service.default_voice_settings()
        audio_bytes = await self.tts_service.generate_audio(
            text=text,
            voice_id=voice_id,
            model=model,
            voice_settings=vs,
        )
        return audio_bytes

    def _upload_public(self, path: str, data: bytes) -> bool:
        try:
            res = self.tts_service.storage_client.storage.from_(self.bucket_name).upload(
                path=path,
                file=data,
                file_options={
                    "content-type": "audio/wav",
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
                path = f"{self.public_prefix}/{vid}.wav"
                if self._object_exists(path):
                    continue
                # Validate language and gender using catalog
                item = self._validate_language_and_gender(vid)
                if not item:
                    continue
                # Select text by language + gender
                langs = item.get("languages") or []
                primary_lang = langs[0] if langs else None
                gender = item.get("gender")
                chosen_text = preview_text or self._preview_text_for(primary_lang, gender)
                console_logger.info(f"Generating preview for voice {vid}")
                audio_bytes = await self._generate_preview_bytes(vid, chosen_text)
                wav_bytes = self._pcm16_to_wav(audio_bytes)
                ok = self._upload_public(path, wav_bytes)
                if not ok:
                    console_logger.warning(f"Upload failed for preview {vid}")
            except Exception as e:
                console_logger.error(f"Error ensuring preview for {vid}: {e}")

    def build_preview_url(self, voice_id: str) -> str:
        path = f"{self.public_prefix}/{voice_id}.wav"
        return self._public_url(path)

    def _preview_text_for(self, primary_language, gender) -> str:
        try:
            if primary_language == LanguageEnum.GERMAN:
                if gender == GenderEnum.FEMALE:
                    return self.preview_text_de_female
                return self.preview_text_de_male
            # Default English for unknowns/others
            if gender == GenderEnum.FEMALE:
                return self.preview_text_en_female
            return self.preview_text_en_male
        except Exception:
            return self.preview_text_en_male

    async def ensure_previews_for_catalog(self, voices_catalog: List[Dict[str, Any]]) -> None:
        """Ensure previews using primary language (first in languages list) per voice.

        voices_catalog items must contain: id (str), languages (List[LanguageEnum]).
        """
        for item in voices_catalog:
            vid = item.get("id")
            langs = item.get("languages") or []
            gender = item.get("gender")
            if not langs or not isinstance(langs[0], LanguageEnum) or gender not in (GenderEnum.MALE, GenderEnum.FEMALE):
                console_logger.warning(f"Skipping preview for {vid}: invalid language/gender metadata")
                continue
            primary_lang = langs[0] if langs else None
            text = self._preview_text_for(primary_lang, gender)
            try:
                path = f"{self.public_prefix}/{vid}.wav"
                if self._object_exists(path):
                    continue
                console_logger.info(f"Generating preview for voice {vid} (lang: {primary_lang})")
                audio_bytes = await self._generate_preview_bytes(vid, text)
                wav_bytes = self._pcm16_to_wav(audio_bytes)
                ok = self._upload_public(path, wav_bytes)
                if not ok:
                    console_logger.warning(f"Upload failed for preview {vid}")
            except Exception as e:
                console_logger.error(f"Error ensuring preview for {vid}: {e}")


