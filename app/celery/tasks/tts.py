from __future__ import annotations

import asyncio
import io
import os
import time
from typing import Any, Awaitable, Dict, Optional

import wave
import threading
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from supabase import Client, create_client

from app.celery.config import celery_app
from app.core.config import settings
from app.core.logging import console_logger
from app.core.database import get_session_maker
from app.core.utils.enums import ElevenLabsModelEnum, VoiceLineAudioStatusEnum
from app.core.utils.audio import pcm16_to_wav_with_tempo
from app.core.utils.tts_common import (
    compute_text_hash,
    compute_settings_hash,
    compute_content_hash,
    private_voice_line_storage_path,
)
from app.models.voice_line_audio import VoiceLineAudio
from sqlalchemy import select


_LOOP_LOCK = threading.Lock()
_ASYNC_LOOP: asyncio.AbstractEventLoop | None = None


def _run_in_loop(coro: Awaitable[Any]) -> Any:
    """Run the given coroutine on a persistent event loop per worker."""
    global _ASYNC_LOOP
    with _LOOP_LOCK:
        if _ASYNC_LOOP is None or _ASYNC_LOOP.is_closed():
            _ASYNC_LOOP = asyncio.new_event_loop()
            asyncio.set_event_loop(_ASYNC_LOOP)
        loop = _ASYNC_LOOP

    if loop.is_running():  # pragma: no cover - defensive; should not happen in Celery worker
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    return loop.run_until_complete(coro)


# ---- Minimal, service-independent helpers ----

def _pcm16_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    # Reuse shared utility which also applies tempo based on TTS_TEMPO env (default 1.1)
    return pcm16_to_wav_with_tempo(pcm_bytes, sample_rate=sample_rate, channels=channels, tempo=None)


def _private_storage_path(user_id: str, voice_line_id: int) -> str:
    return private_voice_line_storage_path(user_id, voice_line_id)


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
    stage_start = time.perf_counter()
    console_logger.info(
        f"[Celery][vl={voice_line_id}] Mark asset start status={status} content_hash={content_hash[:8]}"
    )
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
    elapsed = time.perf_counter() - stage_start
    console_logger.info(
        f"[Celery][vl={voice_line_id}] Mark asset done status={status} took={elapsed:.2f}s"
    )


@celery_app.task(name="tts.generate_voice_line", bind=True, soft_time_limit=180)
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
            console_logger.info(
                f"[Celery] TTS start vl={voice_line_id} voice_id={voice_id} model={model}"
            )
            stage_start = time.perf_counter()
            console_logger.info(f"[Celery][vl={voice_line_id}] Stage=generate_tts_bytes start")
            try:
                pcm = await _generate_tts_bytes(text, voice_id, model, voice_settings)
            except Exception:
                console_logger.exception(f"[Celery][vl={voice_line_id}] Stage=generate_tts_bytes failed")
                raise
            console_logger.info(
                f"[Celery][vl={voice_line_id}] Stage=generate_tts_bytes done took={time.perf_counter() - stage_start:.2f}s"
            )

            stage_start = time.perf_counter()
            console_logger.info(f"[Celery][vl={voice_line_id}] Stage=pcm_to_wav start")
            try:
                wav_bytes = _pcm16_to_wav(pcm)
            except Exception:
                console_logger.exception(f"[Celery][vl={voice_line_id}] Stage=pcm_to_wav failed")
                raise
            console_logger.info(
                f"[Celery][vl={voice_line_id}] Stage=pcm_to_wav done took={time.perf_counter() - stage_start:.2f}s"
            )

            stage_start = time.perf_counter()
            console_logger.info(f"[Celery][vl={voice_line_id}] Stage=calculate_duration start")
            try:
                import wave
                import contextlib
                import io
                with contextlib.closing(wave.open(io.BytesIO(wav_bytes), 'rb')) as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    duration_ms = int((frames / float(rate)) * 1000)
            except Exception:
                console_logger.exception(f"[Celery][vl={voice_line_id}] Stage=calculate_duration failed")
                raise
            console_logger.info(
                f"[Celery][vl={voice_line_id}] Stage=calculate_duration done took={time.perf_counter() - stage_start:.2f}s"
            )

            storage_path = _private_storage_path(user_id, voice_line_id)
            stage_start = time.perf_counter()
            console_logger.info(f"[Celery][vl={voice_line_id}] Stage=upload_supabase start path={storage_path}")
            try:
                await _upload_wav_to_supabase(wav_bytes, storage_path)
            except Exception:
                console_logger.exception(f"[Celery][vl={voice_line_id}] Stage=upload_supabase failed")
                raise
            console_logger.info(
                f"[Celery][vl={voice_line_id}] Stage=upload_supabase done took={time.perf_counter() - stage_start:.2f}s"
            )

            stage_start = time.perf_counter()
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
            console_logger.info(
                f"[Celery][vl={voice_line_id}] Stage=mark_ready done took={time.perf_counter() - stage_start:.2f}s"
            )
            console_logger.info(f"[Celery] TTS ready vl={voice_line_id}")

    try:
        _run_in_loop(_run_once())
    except Exception as e:
        console_logger.exception(f"[Celery] TTS task failed vl={payload.get('voice_line_id')} error={e}")
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

        _run_in_loop(_mark_failed())
        raise
