from __future__ import annotations

import asyncio
import io
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import wave
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from supabase import Client, create_client

from app.celery.config import celery_app
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
import os
import uuid

DATABASE_URL = (
    settings.DATABASE_URL
    .replace("postgresql://", "postgresql+asyncpg://")
    .replace("postgres://", "postgresql+asyncpg://")
)

_ENGINE = None
_ENGINE_PID = None
_SESSION_MAKER = None

def get_engine():
    global _ENGINE, _ENGINE_PID
    pid = os.getpid()
    if _ENGINE is None or _ENGINE_PID != pid:
        _ENGINE = create_async_engine(
            DATABASE_URL,
            poolclass=NullPool,  # oder: pool_size=5, max_overflow=0 für kleine Pools
        )
        _ENGINE_PID = pid
    return _ENGINE

def get_session_maker():
    global _SESSION_MAKER, _ENGINE_PID
    pid = os.getpid()
    if _SESSION_MAKER is None or _ENGINE_PID != pid:
        engine = get_engine()
        _SESSION_MAKER = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return _SESSION_MAKER
from app.core.logging import console_logger
from app.core.database import get_session_maker
from app.core.utils.enums import ElevenLabsModelEnum, VoiceLineAudioStatusEnum
from app.models.voice_line_audio import VoiceLineAudio
from sqlalchemy import select


# ---- Minimal, service-independent helpers ----

def _sha256(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    return (text or "").strip()


def compute_text_hash(text: str) -> str:
    return _sha256(_normalize_text(text))


def compute_settings_hash(voice_id: str, model: ElevenLabsModelEnum, voice_settings: Optional[Dict[str, Any]]) -> str:
    payload = {
        "voice_id": voice_id,
        "model_id": model.value if isinstance(model, ElevenLabsModelEnum) else model,
        "voice_settings": voice_settings or {},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256(canonical)


def compute_content_hash(text: str, voice_id: str, model: ElevenLabsModelEnum, voice_settings: Optional[Dict[str, Any]]) -> str:
    return _sha256(f"{compute_text_hash(text)}|{compute_settings_hash(voice_id, model, voice_settings)}")


def _pcm16_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def _private_storage_path(user_id: str, voice_line_id: int) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"private/{user_id}/voice_lines/{voice_line_id}_{ts}_{uuid.uuid4().hex[:8]}.wav"


async def _generate_tts_bytes(text: str, voice_id: str, model: ElevenLabsModelEnum, voice_settings: Optional[Dict[str, Any]]) -> bytes:
    client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)

    def _convert_sync() -> bytes:
        gen = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            voice_settings=VoiceSettings(**(voice_settings or {})),
            model_id=model.value if isinstance(model, ElevenLabsModelEnum) else str(model),
            output_format="pcm_16000",
        )
        return b"".join(gen)

    # Single attempt; let Celery handle retries between attempts
    return await asyncio.to_thread(_convert_sync)


async def _upload_wav_to_supabase(wav_bytes: bytes, path: str) -> None:
    client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

    def _upload_sync():
        return client.storage.from_("voice-lines").upload(
            path=path,
            file=wav_bytes,
            file_options={
                "content-type": "audio/wav",
                "cache-control": "3600",
                "upsert": "false",
            },
        )

    _ = await asyncio.to_thread(_upload_sync)


async def _mark_asset(db_session, voice_line_id: int, content_hash: str, status: VoiceLineAudioStatusEnum,
                      storage_path: Optional[str] = None, error: Optional[str] = None,
                      voice_id: Optional[str] = None, model: Optional[ElevenLabsModelEnum] = None,
                      voice_settings: Optional[Dict[str, Any]] = None, text: Optional[str] = None,
                      duration_ms: Optional[int] = None) -> None:
    r = await db_session.execute(
        select(VoiceLineAudio).where(
            VoiceLineAudio.voice_line_id == voice_line_id,
            VoiceLineAudio.content_hash == content_hash,
            VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
        ).limit(1)
    )
    pending = r.scalar_one_or_none()
    if pending:
        pending.status = status
        pending.storage_path = storage_path if storage_path else pending.storage_path
        pending.error = error
        if voice_id:
            pending.voice_id = voice_id
        if model:
            pending.model_id = model
        if voice_settings is not None:
            pending.voice_settings = voice_settings
        if text is not None:
            pending.text_hash = compute_text_hash(text)
            pending.settings_hash = compute_settings_hash(voice_id or pending.voice_id, model or pending.model_id, voice_settings)
        if duration_ms is not None:
            pending.duration_ms = duration_ms
        await db_session.commit()


@celery_app.task(name="tts.generate_voice_line", bind=True, rate_limit="10/m", soft_time_limit=180)
def generate_voice_line_task(self, payload: Dict[str, Any]) -> None:
    """Generate TTS WAV and store it, then mark the PENDING asset READY/FAILED.

    Expected payload keys (JSON-serializable):
      - voice_line_id: int
      - user_id: str
      - text: str
      - voice_id: str
      - model: str (ElevenLabsModelEnum value)
      - voice_settings: dict
      - content_hash: str
    """

    async def _run_once() -> None:
        model = ElevenLabsModelEnum(payload["model"]) if isinstance(payload.get("model"), str) else payload["model"]
        text: str = payload["text"]
        voice_id: str = payload["voice_id"]
        user_id: str = payload["user_id"]
        voice_line_id: int = int(payload["voice_line_id"])
        content_hash: str = payload["content_hash"]
        voice_settings = payload.get("voice_settings") or {}

        async with get_session_maker()() as db_session:
            console_logger.info(f"[Celery] TTS start vl={voice_line_id}")
            pcm = await _generate_tts_bytes(text, voice_id, model, voice_settings)
            wav_bytes = _pcm16_to_wav(pcm)
            # Calculate duration in ms
            import wave
            import contextlib
            import io
            with contextlib.closing(wave.open(io.BytesIO(wav_bytes), 'rb')) as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration_ms = int((frames / float(rate)) * 1000)
            storage_path = _private_storage_path(user_id, voice_line_id)
            await _upload_wav_to_supabase(wav_bytes, storage_path)
            await _mark_asset(
                db_session,
                voice_line_id=voice_line_id,
                content_hash=content_hash,
                status=VoiceLineAudioStatusEnum.READY,
                storage_path=storage_path,
                voice_id=voice_id,
                model=model,
                voice_settings=voice_settings,
                text=text,
                duration_ms=duration_ms,
            )
            console_logger.info(f"[Celery] TTS ready vl={voice_line_id}")

    try:
        asyncio.run(_run_once())
    except Exception as e:
        max_retries = int(os.getenv("TTS_TASK_MAX_RETRIES", "5"))
        retries = getattr(self.request, "retries", 0)
        if retries < max_retries:
            countdown = min(30, 2 ** retries)
            raise self.retry(exc=e, countdown=countdown, max_retries=max_retries)

        async def _mark_failed() -> None:
            async with get_session_maker()() as db_session:
                await _mark_asset(
                    db_session,
                    voice_line_id=int(payload.get("voice_line_id", 0)),
                    content_hash=str(payload.get("content_hash", "")),
                    status=VoiceLineAudioStatusEnum.FAILED,
                    error=str(e),
                )

        asyncio.run(_mark_failed())
        raise


