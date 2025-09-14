import io
import os
from typing import Optional

from pydub import AudioSegment

from app.core.logging import console_logger


# Default tempo multiplier for generated WAV audio (1.0 = unchanged)
# Can be overridden via environment variable TTS_TEMPO
TTS_DEFAULT_TEMPO: float = float(os.getenv("TTS_TEMPO", "1.1"))


def apply_tempo(wav_bytes: bytes, tempo: Optional[float]) -> bytes:
    """Apply pitch-preserving tempo adjustment using ffmpeg's atempo filter.

    When tempo is None or ~1.0, the input is returned unchanged. Errors are swallowed
    and the original WAV is returned to avoid failing the whole pipeline.
    """
    try:
        if tempo is None or abs(float(tempo) - 1.0) < 1e-3:
            return wav_bytes
        clamped = max(0.5, min(2.0, float(tempo)))
        seg = AudioSegment.from_file(io.BytesIO(wav_bytes), format="wav")
        out = io.BytesIO()
        seg.export(out, format="wav", parameters=["-filter:a", f"atempo={clamped:.3f}"])
        return out.getvalue()
    except Exception as e:
        console_logger.warning(f"Tempo adjustment failed; returning original WAV. Error: {e}")
        return wav_bytes


def pcm16_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wrap raw PCM16 bytes in a minimal WAV container with given sample rate/channels."""
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def pcm16_to_wav_with_tempo(
    pcm_bytes: bytes,
    sample_rate: int = 16000,
    channels: int = 1,
    tempo: Optional[float] = None,
) -> bytes:
    """Convert PCM16 to WAV and apply pitch-preserving tempo.

    If tempo is None, uses TTS_DEFAULT_TEMPO; otherwise uses the provided tempo.
    """
    wav_bytes = pcm16_to_wav(pcm_bytes, sample_rate=sample_rate, channels=channels)
    effective_tempo = TTS_DEFAULT_TEMPO if tempo is None else tempo
    return apply_tempo(wav_bytes, effective_tempo)


