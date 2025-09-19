"""Redis-backed tracking for audio generation progress per scenario/voice."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, Optional, Tuple

from app.core.utils.enums import VoiceLineAudioStatusEnum
from app.services.cache_service import CacheService


class AudioProgressService:
    """Small helper to store per-scenario audio generation progress snapshots."""

    _PREFIX = "audio:progress"
    _TTL_SECONDS = 3600  # 1 hour

    @classmethod
    def _cache_key(cls, scenario_id: int, voice_id: Optional[str]) -> str:
        suffix = voice_id or "default"
        return f"{scenario_id}:{suffix}"

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _coerce_status(status: VoiceLineAudioStatusEnum | str) -> str:
        if isinstance(status, VoiceLineAudioStatusEnum):
            return status.name
        return str(status or VoiceLineAudioStatusEnum.PENDING.name)

    @classmethod
    def _compute_counts(cls, statuses: Dict[str, str]) -> Dict[str, int]:
        ready = sum(1 for s in statuses.values() if s == VoiceLineAudioStatusEnum.READY.name)
        failed = sum(1 for s in statuses.values() if s == VoiceLineAudioStatusEnum.FAILED.name)
        pending = sum(1 for s in statuses.values() if s == VoiceLineAudioStatusEnum.PENDING.name)
        return {
            "ready": ready,
            "failed": failed,
            "pending": pending,
        }

    @classmethod
    async def initialize(
        cls,
        scenario_id: int,
        voice_id: Optional[str],
        voice_line_ids: Iterable[int],
    ) -> None:
        ids = list(voice_line_ids)
        if not ids:
            return
        statuses = {str(vl_id): VoiceLineAudioStatusEnum.PENDING.name for vl_id in ids}
        data = {
            "scenario_id": scenario_id,
            "voice_id": voice_id,
            "total": len(ids),
            "statuses": statuses,
            "counts": cls._compute_counts(statuses),
            "updated_at": cls._utc_now_iso(),
        }
        cache = await CacheService.get_global()
        await cache.set_json(
            cls._cache_key(scenario_id, voice_id),
            data,
            ttl=cls._TTL_SECONDS,
            prefix=cls._PREFIX,
        )

    @classmethod
    async def ensure_initialized(
        cls,
        scenario_id: int,
        voice_id: Optional[str],
        voice_line_ids: Iterable[int],
    ) -> None:
        cache = await CacheService.get_global()
        key = cls._cache_key(scenario_id, voice_id)
        existing = await cache.get_json(key, prefix=cls._PREFIX)
        if existing:
            statuses: Dict[str, str] = existing.setdefault("statuses", {})
            missing = False
            for vl_id in voice_line_ids:
                str_id = str(vl_id)
                if str_id not in statuses:
                    statuses[str_id] = VoiceLineAudioStatusEnum.PENDING.name
                    missing = True
            if missing:
                existing["total"] = len(statuses)
                existing["counts"] = cls._compute_counts(statuses)
                existing["updated_at"] = cls._utc_now_iso()
                await cache.set_json(key, existing, ttl=cls._TTL_SECONDS, prefix=cls._PREFIX)
            return
        await cls.initialize(scenario_id, voice_id, voice_line_ids)

    @classmethod
    async def update_status(
        cls,
        scenario_id: int,
        voice_id: Optional[str],
        voice_line_id: int,
        status: VoiceLineAudioStatusEnum | str,
    ) -> None:
        cache = await CacheService.get_global()
        key = cls._cache_key(scenario_id, voice_id)
        data = await cache.get_json(key, prefix=cls._PREFIX)
        if not data:
            # Nothing initialized yet; create minimal snapshot with single entry.
            await cls.initialize(scenario_id, voice_id, [voice_line_id])
            data = await cache.get_json(key, prefix=cls._PREFIX)
            if not data:
                return
        statuses: Dict[str, str] = data.setdefault("statuses", {})
        statuses[str(voice_line_id)] = cls._coerce_status(status)
        data["counts"] = cls._compute_counts(statuses)
        data["updated_at"] = cls._utc_now_iso()
        if data["counts"].get("ready", 0) == data.get("total", 0) and data["counts"].get("failed", 0) == 0:
            data["completed_at"] = data["updated_at"]
        elif "completed_at" in data:
            data.pop("completed_at", None)
        await cache.set_json(key, data, ttl=cls._TTL_SECONDS, prefix=cls._PREFIX)

    @classmethod
    async def bulk_update(
        cls,
        scenario_id: int,
        voice_id: Optional[str],
        updates: Dict[int, VoiceLineAudioStatusEnum | str],
    ) -> None:
        if not updates:
            return
        cache = await CacheService.get_global()
        key = cls._cache_key(scenario_id, voice_id)
        data = await cache.get_json(key, prefix=cls._PREFIX)
        if not data:
            await cls.initialize(scenario_id, voice_id, updates.keys())
            data = await cache.get_json(key, prefix=cls._PREFIX)
            if not data:
                return
        statuses: Dict[str, str] = data.setdefault("statuses", {})
        for vl_id, status in updates.items():
            statuses[str(vl_id)] = cls._coerce_status(status)
        data["total"] = len(statuses)
        data["counts"] = cls._compute_counts(statuses)
        data["updated_at"] = cls._utc_now_iso()
        if data["counts"].get("ready", 0) == data.get("total", 0) and data["counts"].get("failed", 0) == 0:
            data["completed_at"] = data["updated_at"]
        elif "completed_at" in data:
            data.pop("completed_at", None)
        await cache.set_json(key, data, ttl=cls._TTL_SECONDS, prefix=cls._PREFIX)

    @classmethod
    async def get_progress(cls, scenario_id: int, voice_id: Optional[str]) -> Optional[Dict[str, object]]:
        cache = await CacheService.get_global()
        return await cache.get_json(cls._cache_key(scenario_id, voice_id), prefix=cls._PREFIX)

    @classmethod
    async def get_latest_progress(cls, scenario_id: int) -> Optional[Dict[str, object]]:
        """Return the freshest progress snapshot for the scenario across all voices."""
        cache = await CacheService.get_global()
        client = cache.client
        if client is None:
            return None

        match_pattern = cache._k(f"{cls._PREFIX}:{scenario_id}:*")
        latest: Optional[Tuple[str, Dict[str, object]]] = None

        async for full_key in client.scan_iter(match=match_pattern):
            try:
                suffix = full_key.split(f"{cache.prefix}:{cls._PREFIX}:", 1)[1]
            except IndexError:
                continue
            progress = await cache.get_json(suffix, prefix=cls._PREFIX)
            if not progress:
                continue
            updated_at = progress.get("updated_at") or ""
            if latest is None or updated_at > latest[1].get("updated_at", ""):
                latest = (suffix, progress)

        return latest[1] if latest else None

    @classmethod
    async def clear(cls, scenario_id: int, voice_id: Optional[str]) -> None:
        cache = await CacheService.get_global()
        await cache.delete(cls._cache_key(scenario_id, voice_id), prefix=cls._PREFIX)
