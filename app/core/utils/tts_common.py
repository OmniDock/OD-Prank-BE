from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.utils.enums import ElevenLabsModelEnum


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    return (text or "").strip()


def compute_text_hash(text: str) -> str:
    return sha256_hex(normalize_text(text))


def compute_settings_hash(
    voice_id: str,
    model: ElevenLabsModelEnum | str,
    voice_settings: Optional[Dict[str, Any]],
) -> str:
    payload = {
        "voice_id": voice_id,
        "model_id": model.value if isinstance(model, ElevenLabsModelEnum) else str(model),
        "voice_settings": voice_settings or {},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_hex(canonical)


def compute_content_hash(
    text: str,
    voice_id: str,
    model: ElevenLabsModelEnum | str,
    voice_settings: Optional[Dict[str, Any]],
) -> str:
    return sha256_hex(f"{compute_text_hash(text)}|{compute_settings_hash(voice_id, model, voice_settings)}")


def private_voice_line_storage_path(user_id: str, voice_line_id: int) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"private/{user_id}/voice_lines/{voice_line_id}_{ts}_{uuid.uuid4().hex[:8]}.wav"


