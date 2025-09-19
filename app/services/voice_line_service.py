import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional

from sqlalchemy import select, func, and_

from app.core.database import AsyncSession
from app.core.auth import AuthUser
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.voice_line_repository import VoiceLineRepository
from app.models.voice_line_audio import VoiceLineAudio
from app.models.voice_line import VoiceLine
from app.services.tts_service import TTSService
from app.services.audio_progress_service import AudioProgressService
from app.core.utils.enums import ElevenLabsModelEnum, VoiceLineAudioStatusEnum
import hashlib
import json


from app.core.logging import console_logger
from sqlalchemy import select


async def background_generate_and_store_audio(
    voice_line_id: int,
    user_id: str,
    text: str,
    voice_id: str,
    model: ElevenLabsModelEnum,
    voice_settings: dict,
    content_hash: str,
):
    """Background task to generate and store TTS audio and update PENDING -> READY/FAILED."""
    # Lazy import to avoid circular: get_db_session
    from app.core.database import get_db_session

    try:
        console_logger.info(f"Background TTS generation started for voice line {voice_line_id}")

        async for db_session in get_db_session():
            try:
                tts_service = TTSService()

                success, signed_url, storage_path, error_msg = await tts_service.generate_and_store_audio(
                    text=text,
                    voice_line_id=voice_line_id,
                    user_id=user_id,
                    voice_id=voice_id,
                    model=model,
                    voice_settings=voice_settings,
                )

                pending_result = await db_session.execute(
                    select(VoiceLineAudio).where(
                        VoiceLineAudio.voice_line_id == voice_line_id,
                        VoiceLineAudio.content_hash == content_hash,
                        VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
                    ).limit(1)
                )
                pending: VoiceLineAudio | None = pending_result.scalar_one_or_none()

                if success and storage_path:
                    if pending:
                        pending.storage_path = storage_path
                        pending.status = VoiceLineAudioStatusEnum.READY
                        pending.error = None
                        pending.voice_id = voice_id
                        pending.model_id = model
                        pending.voice_settings = voice_settings
                        pending.text_hash = tts_service.compute_text_hash(text)
                        pending.settings_hash = tts_service.compute_settings_hash(voice_id, model, voice_settings)
                        await db_session.commit()
                        console_logger.info(
                            f"Background TTS generation completed for voice line {voice_line_id} (updated PENDING->READY)"
                        )
                    else:
                        asset = VoiceLineAudio(
                            voice_line_id=voice_line_id,
                            voice_id=voice_id,
                            model_id=model,
                            voice_settings=voice_settings,
                            storage_path=storage_path,
                            duration_ms=None,
                            size_bytes=None,
                            text_hash=tts_service.compute_text_hash(text),
                            settings_hash=tts_service.compute_settings_hash(voice_id, model, voice_settings),
                            content_hash=content_hash,
                            status=VoiceLineAudioStatusEnum.READY,
                        )
                        db_session.add(asset)
                        await db_session.commit()
                        console_logger.info(
                            f"Background TTS generation completed for voice line {voice_line_id} (created READY)"
                        )
                else:
                    if pending:
                        pending.status = VoiceLineAudioStatusEnum.FAILED
                        pending.error = error_msg or "TTS generation failed"
                        await db_session.commit()
                        console_logger.error(
                            f"Background TTS generation failed for voice line {voice_line_id}: {error_msg}"
                        )
                    else:
                        console_logger.error(
                            f"Background TTS failed and no PENDING record found for voice line {voice_line_id}: {error_msg}"
                        )

            except Exception as e:
                console_logger.error(f"Background TTS generation error for voice line {voice_line_id}: {str(e)}")
                await db_session.rollback()
            finally:
                await db_session.close()
                break

    except Exception as e:
        console_logger.error(f"Background TTS task setup failed for voice line {voice_line_id}: {str(e)}")


class VoiceLineService:
    """Business logic for voice lines and their audio assets."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.scenario_repo = ScenarioRepository(db_session)
        self.voice_line_repo = VoiceLineRepository(db_session)
        self.tts_service = TTSService()
        self._max_retry_attempts = int(os.getenv("TTS_MAX_RETRY_ATTEMPTS", "3"))
        self._stale_pending_seconds = int(os.getenv("TTS_PENDING_STALE_SECONDS", "120"))

    async def build_audio_summary(self, user: AuthUser, scenario_id: int) -> Tuple[Dict, str]:
        """Return { items: [...] } and an ETag string.

        Each item: { voice_line_id, status, signed_url, storage_path, updated_at }
        """
        scenario = await self.scenario_repo.get_scenario_by_id(scenario_id, user.id_str)
        if not scenario:
            raise ValueError("Scenario not found or access denied")

        vl_ids_result = await self.db.execute(
            select(VoiceLine.id).where(VoiceLine.scenario_id == scenario_id)
        )
        voice_line_ids = [row[0] for row in vl_ids_result.all()]

        items: List[Dict] = []
        progress_statuses: Dict[int, str] = {}
        cached_progress = await AudioProgressService.get_latest_progress(scenario_id)
        if cached_progress:
            raw_statuses = cached_progress.get("statuses", {}) or {}
            progress_statuses = {
                int(vlid): status
                for vlid, status in raw_statuses.items()
                if status not in (None, "")
            }

        if voice_line_ids:
            latest_subq = (
                select(
                    VoiceLineAudio.voice_line_id.label("vlid"),
                    func.max(VoiceLineAudio.updated_at).label("max_updated")
                )
                .where(VoiceLineAudio.voice_line_id.in_(voice_line_ids))
                .group_by(VoiceLineAudio.voice_line_id)
                .subquery()
            )

            latest_rows_result = await self.db.execute(
                select(VoiceLineAudio)
                .join(latest_subq, and_(
                    VoiceLineAudio.voice_line_id == latest_subq.c.vlid,
                    VoiceLineAudio.updated_at == latest_subq.c.max_updated
                ))
            )
            latest_by_vl = {r.voice_line_id: r for r in latest_rows_result.scalars().all()}

            # Avoid rolling back here to prevent expiring loaded ORM objects during serialization

            signed_cache: Dict[str, str] = {}
            for vlid in sorted(voice_line_ids):
                audio = latest_by_vl.get(vlid)
                status = audio.status.value if audio else None
                storage_path = audio.storage_path if audio else None
                updated_at = (audio.updated_at.isoformat() if audio else "0")
                signed_url = None
                if audio and getattr(audio.status, "name", None) == "READY" and storage_path:
                    if storage_path in signed_cache:
                        signed_url = signed_cache[storage_path]
                    else:
                        try:
                            signed_url = await self.tts_service.get_audio_url(storage_path)
                            if signed_url:
                                signed_cache[storage_path] = signed_url
                        except Exception:
                            signed_url = None
                derived_status = progress_statuses.get(vlid)
                if derived_status:
                    status = derived_status
                items.append({
                    "voice_line_id": vlid,
                    "status": status,
                    "signed_url": signed_url,
                    "storage_path": storage_path,
                    "updated_at": updated_at,
                })

        canonical_items = sorted([
            {
                "voice_line_id": it["voice_line_id"],
                "status": it["status"] or "",
                "storage_path": it["storage_path"] or "",
                "updated_at": it["updated_at"] or "",
            }
            for it in items
        ], key=lambda x: x["voice_line_id"])
        canonical = json.dumps(canonical_items, separators=(",", ":"), ensure_ascii=False)
        etag = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        return {"items": items}, etag

    async def request_tts_single(
        self,
        user: AuthUser,
        voice_line_id: int,
        voice_id: str,
        *,
        auto_commit: bool = True,
    ) -> Dict:
        """Prepare or reuse TTS for a single voice line.
        Returns a dict describing current status and optional payload for background generation.
        """
        if not voice_id:
            raise ValueError("voice_id is required")

        voice_line = await self.voice_line_repo.get_voice_line_by_id_with_user_check(voice_line_id, user.id_str)
        if not voice_line:
            raise ValueError("Voice line not found or access denied")

        scenario_id = voice_line.scenario_id
        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(seconds=self._stale_pending_seconds)

        base_voice_settings = self.tts_service.default_voice_settings(voice_id)
        default_model = ElevenLabsModelEnum.ELEVEN_TTV_V3
        base_content_hash = self.tts_service.compute_content_hash(
            voice_line.text,
            voice_id,
            default_model,
            base_voice_settings,
        )

        # Reuse READY with matching content hash
        ready_result = await self.db.execute(
            select(VoiceLineAudio).where(
                VoiceLineAudio.voice_line_id == voice_line_id,
                VoiceLineAudio.content_hash == base_content_hash,
                VoiceLineAudio.status == VoiceLineAudioStatusEnum.READY,
            ).limit(1)
        )
        ready_asset: Optional[VoiceLineAudio] = ready_result.scalar_one_or_none()
        if ready_asset and ready_asset.storage_path:
            signed_url = await self.tts_service.get_audio_url(ready_asset.storage_path)
            return {
                "status": "ready",
                "voice_line_id": voice_line_id,
                "signed_url": signed_url,
                "storage_path": ready_asset.storage_path,
            }

        # Check for in-progress asset
        pending_result = await self.db.execute(
            select(VoiceLineAudio).where(
                VoiceLineAudio.voice_line_id == voice_line_id,
                VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
                VoiceLineAudio.voice_id == voice_id,
            ).order_by(VoiceLineAudio.updated_at.desc()).limit(1)
        )
        pending_asset: Optional[VoiceLineAudio] = pending_result.scalar_one_or_none()
        if pending_asset:
            if pending_asset.updated_at and pending_asset.updated_at >= stale_cutoff:
                return {"status": "in_progress", "voice_line_id": voice_line_id}
            if (pending_asset.retry_attempts or 0) >= self._max_retry_attempts:
                return {
                    "status": "retry_exhausted",
                    "voice_line_id": voice_line_id,
                    "error_message": f"Retry limit reached ({self._max_retry_attempts})",
                }

        # Check for most recent FAILED asset for this voice
        failed_result = await self.db.execute(
            select(VoiceLineAudio).where(
                VoiceLineAudio.voice_line_id == voice_line_id,
                VoiceLineAudio.voice_id == voice_id,
                VoiceLineAudio.status == VoiceLineAudioStatusEnum.FAILED,
            ).order_by(VoiceLineAudio.updated_at.desc()).limit(1)
        )
        failed_asset: Optional[VoiceLineAudio] = failed_result.scalar_one_or_none()

        generation_voice_settings = base_voice_settings
        generation_model = default_model

        if pending_asset and pending_asset.updated_at and pending_asset.updated_at < stale_cutoff:
            # Requeue stale pending asset
            generation_voice_settings = pending_asset.voice_settings or base_voice_settings
            generation_model = pending_asset.model_id or default_model
            pending_asset.status = VoiceLineAudioStatusEnum.PENDING
            pending_asset.error = None
            pending_asset.storage_path = None
            pending_asset.duration_ms = None
            pending_asset.size_bytes = None
            pending_asset.voice_id = voice_id
            pending_asset.voice_settings = generation_voice_settings
            pending_asset.model_id = generation_model
            pending_asset.text_hash = self.tts_service.compute_text_hash(voice_line.text)
            pending_asset.settings_hash = self.tts_service.compute_settings_hash(
                voice_id, generation_model, generation_voice_settings
            )
            pending_asset.content_hash = self.tts_service.compute_content_hash(
                voice_line.text,
                voice_id,
                generation_model,
                generation_voice_settings,
            )
            pending_asset.updated_at = now
            if auto_commit:
                await self.db.commit()

            payload = {
                "voice_line_id": voice_line_id,
                "user_id": user.id_str,
                "text": voice_line.text,
                "voice_id": voice_id,
                "model": generation_model,
                "voice_settings": generation_voice_settings,
                "content_hash": pending_asset.content_hash,
                "scenario_id": scenario_id,
            }
            return {"status": "created_pending", "voice_line_id": voice_line_id, "background_payload": payload}

        if failed_asset:
            attempts = failed_asset.retry_attempts or 0
            if attempts >= self._max_retry_attempts:
                return {
                    "status": "retry_exhausted",
                    "voice_line_id": voice_line_id,
                    "error_message": f"Retry limit reached ({self._max_retry_attempts})",
                }
            generation_voice_settings = failed_asset.voice_settings or base_voice_settings
            generation_model = failed_asset.model_id or default_model
            failed_asset.status = VoiceLineAudioStatusEnum.PENDING
            failed_asset.error = None
            failed_asset.storage_path = None
            failed_asset.duration_ms = None
            failed_asset.size_bytes = None
            failed_asset.voice_id = voice_id
            failed_asset.voice_settings = generation_voice_settings
            failed_asset.model_id = generation_model
            failed_asset.text_hash = self.tts_service.compute_text_hash(voice_line.text)
            failed_asset.settings_hash = self.tts_service.compute_settings_hash(
                voice_id, generation_model, generation_voice_settings
            )
            failed_asset.content_hash = self.tts_service.compute_content_hash(
                voice_line.text,
                voice_id,
                generation_model,
                generation_voice_settings,
            )
            failed_asset.updated_at = now
            if auto_commit:
                await self.db.commit()

            payload = {
                "voice_line_id": voice_line_id,
                "user_id": user.id_str,
                "text": voice_line.text,
                "voice_id": voice_id,
                "model": generation_model,
                "voice_settings": generation_voice_settings,
                "content_hash": failed_asset.content_hash,
                "scenario_id": scenario_id,
            }
            return {"status": "created_pending", "voice_line_id": voice_line_id, "background_payload": payload}

        # If we previously found a fresh pending asset, respect its state
        if pending_asset:
            return {"status": "in_progress", "voice_line_id": voice_line_id}

        # Create new pending asset
        new_asset = VoiceLineAudio(
            voice_line_id=voice_line_id,
            voice_id=voice_id,
            model_id=default_model,
            voice_settings=base_voice_settings,
            storage_path=None,
            duration_ms=None,
            size_bytes=None,
            text_hash=self.tts_service.compute_text_hash(voice_line.text),
            settings_hash=self.tts_service.compute_settings_hash(voice_id, default_model, base_voice_settings),
            content_hash=base_content_hash,
            status=VoiceLineAudioStatusEnum.PENDING,
            error=None,
        )
        self.db.add(new_asset)
        if auto_commit:
            await self.db.commit()

        payload = {
            "voice_line_id": voice_line_id,
            "user_id": user.id_str,
            "text": voice_line.text,
            "voice_id": voice_id,
            "model": default_model,
            "voice_settings": base_voice_settings,
            "content_hash": base_content_hash,
            "scenario_id": scenario_id,
        }
        return {"status": "created_pending", "voice_line_id": voice_line_id, "background_payload": payload}

    async def request_tts_regenerate(self, user: AuthUser, voice_line_id: int, voice_id: str) -> Dict:
        """Prepare regeneration; similar flow to single."""
        return await self.request_tts_single(user, voice_line_id, voice_id)

    async def request_tts_for_scenario(self, user: AuthUser, scenario_id: int, voice_id: Optional[str]) -> Tuple[List[Dict], List[Dict]]:
        """Prepare TTS for all voice lines in a scenario.
        Returns (results, background_payloads) where results holds entries akin to TTSResult fields.
        """
        scenario = await self.scenario_repo.get_scenario_by_id(scenario_id, user.id_str)
        if not scenario:
            raise ValueError("Scenario not found or access denied")
        voice_lines = await self.voice_line_repo.get_voice_lines_by_scenario_id(scenario_id)
        if not voice_lines:
            raise ValueError("No voice lines found for this scenario")

        results: List[Dict] = []
        payloads: List[Dict] = []

        selected_default_voice_id = voice_id or scenario.preferred_voice_id
        if not selected_default_voice_id:
            raise ValueError("voice_id is required (or set preferred voice on scenario)")

        voice_line_ids = [vl.id for vl in voice_lines]
        await AudioProgressService.ensure_initialized(scenario.id, selected_default_voice_id, voice_line_ids)
        progress_updates: Dict[int, VoiceLineAudioStatusEnum] = {}

        for vl in voice_lines:
            try:
                prepared = await self.request_tts_single(
                    user,
                    vl.id,
                    selected_default_voice_id,
                    auto_commit=False,
                )
                if prepared["status"] == "ready":
                    results.append({
                        "voice_line_id": vl.id,
                        "success": True,
                        "signed_url": prepared.get("signed_url"),
                        "storage_path": prepared.get("storage_path"),
                        "error_message": None,
                    })
                    progress_updates[vl.id] = VoiceLineAudioStatusEnum.READY
                elif prepared["status"] == "in_progress":
                    results.append({
                        "voice_line_id": vl.id,
                        "success": False,
                        "signed_url": None,
                        "storage_path": None,
                        "error_message": "Audio generation already in progress",
                    })
                    progress_updates[vl.id] = VoiceLineAudioStatusEnum.PENDING
                elif prepared["status"] == "retry_exhausted":
                    results.append({
                        "voice_line_id": vl.id,
                        "success": False,
                        "signed_url": None,
                        "storage_path": None,
                        "error_message": prepared.get("error_message") or "Retry limit reached",
                    })
                    progress_updates[vl.id] = VoiceLineAudioStatusEnum.FAILED
                else:
                    # created_pending
                    payloads.append(prepared["background_payload"])
                    results.append({
                        "voice_line_id": vl.id,
                        "success": True,
                        "signed_url": None,
                        "storage_path": None,
                        "error_message": "Audio generation started in background",
                    })
                    progress_updates[vl.id] = VoiceLineAudioStatusEnum.PENDING
            except Exception as e:
                results.append({
                    "voice_line_id": vl.id,
                    "success": False,
                    "signed_url": None,
                    "storage_path": None,
                    "error_message": f"Generation failed: {str(e)}",
                })
                progress_updates[vl.id] = VoiceLineAudioStatusEnum.FAILED

        if progress_updates:
            await AudioProgressService.bulk_update(scenario.id, selected_default_voice_id, progress_updates)

        await self.db.commit()
        return results, payloads

    async def retry_missing_audios(
        self,
        user: AuthUser,
        scenario_id: int,
        voice_id: Optional[str],
    ) -> Tuple[List[Dict], List[Dict]]:
        """Retry generation for voice lines that are missing audio or stuck."""
        scenario = await self.scenario_repo.get_scenario_by_id(scenario_id, user.id_str)
        if not scenario:
            raise ValueError("Scenario not found or access denied")

        voice_lines = await self.voice_line_repo.get_voice_lines_by_scenario_id(scenario_id)
        if not voice_lines:
            raise ValueError("No voice lines found for this scenario")

        chosen_voice_id = voice_id or scenario.preferred_voice_id
        if not chosen_voice_id:
            raise ValueError("voice_id is required (or set preferred voice on scenario)")

        results: List[Dict] = []
        payloads: List[Dict] = []

        await AudioProgressService.ensure_initialized(scenario.id, chosen_voice_id, [vl.id for vl in voice_lines])
        progress_updates: Dict[int, VoiceLineAudioStatusEnum] = {}

        for vl in voice_lines:
            try:
                prepared = await self.request_tts_single(
                    user,
                    vl.id,
                    chosen_voice_id,
                    auto_commit=False,
                )
                status = prepared.get("status")

                if status == "created_pending":
                    payloads.append(prepared["background_payload"])
                    results.append({
                        "voice_line_id": vl.id,
                        "success": True,
                        "signed_url": None,
                        "storage_path": None,
                        "error_message": "Retry scheduled",
                    })
                    progress_updates[vl.id] = VoiceLineAudioStatusEnum.PENDING
                elif status == "ready":
                    results.append({
                        "voice_line_id": vl.id,
                        "success": True,
                        "signed_url": prepared.get("signed_url"),
                        "storage_path": prepared.get("storage_path"),
                        "error_message": None,
                    })
                    progress_updates[vl.id] = VoiceLineAudioStatusEnum.READY
                elif status == "in_progress":
                    results.append({
                        "voice_line_id": vl.id,
                        "success": False,
                        "signed_url": None,
                        "storage_path": None,
                        "error_message": "Audio generation already in progress",
                    })
                    progress_updates[vl.id] = VoiceLineAudioStatusEnum.PENDING
                elif status == "retry_exhausted":
                    results.append({
                        "voice_line_id": vl.id,
                        "success": False,
                        "signed_url": None,
                        "storage_path": None,
                        "error_message": prepared.get("error_message") or "Retry limit reached",
                    })
                    progress_updates[vl.id] = VoiceLineAudioStatusEnum.FAILED
                else:
                    results.append({
                        "voice_line_id": vl.id,
                        "success": False,
                        "signed_url": None,
                        "storage_path": None,
                        "error_message": "Unknown retry outcome",
                    })
                    progress_updates[vl.id] = VoiceLineAudioStatusEnum.PENDING
            except Exception as exc:  # pragma: no cover - defensive logging
                console_logger.error(f"Retry failed for voice line {vl.id}: {exc}")
                results.append({
                    "voice_line_id": vl.id,
                    "success": False,
                    "signed_url": None,
                    "storage_path": None,
                    "error_message": f"Retry failed: {exc}",
                })
                progress_updates[vl.id] = VoiceLineAudioStatusEnum.FAILED

        if progress_updates:
            await AudioProgressService.bulk_update(scenario.id, chosen_voice_id, progress_updates)

        await self.db.commit()
        return results, payloads

    async def get_audio_url_for_voice_line(self, user: AuthUser, voice_line_id: int, expires_in: int = 3600 * 12, voice_id: Optional[str] = None) -> Dict:
        """Return dict with status and optionally signed_url for a voice line's latest READY audio."""
        voice_line = await self.voice_line_repo.get_voice_line_by_id_with_user_check(voice_line_id, user.id_str)
        if not voice_line:
            raise ValueError("Voice line not found or access denied")

        if voice_id:
            text_hash = self.tts_service.compute_text_hash(voice_line.text)
            r = await self.db.execute(
                select(VoiceLineAudio).where(
                    VoiceLineAudio.voice_line_id == voice_line_id,
                    VoiceLineAudio.voice_id == voice_id,
                    VoiceLineAudio.text_hash == text_hash,
                    VoiceLineAudio.status == VoiceLineAudioStatusEnum.READY,
                ).order_by(VoiceLineAudio.created_at.desc()).limit(1)
            )
        else:
            r = await self.db.execute(
                select(VoiceLineAudio).where(
                    VoiceLineAudio.voice_line_id == voice_line_id,
                    VoiceLineAudio.status == VoiceLineAudioStatusEnum.READY,
                ).order_by(VoiceLineAudio.created_at.desc()).limit(1)
            )
        asset: Optional[VoiceLineAudio] = r.scalar_one_or_none()

        if not asset or not asset.storage_path:
            # Check PENDING
            if voice_id:
                pending_r = await self.db.execute(
                    select(VoiceLineAudio).where(
                        VoiceLineAudio.voice_line_id == voice_line_id,
                        VoiceLineAudio.voice_id == voice_id,
                        VoiceLineAudio.text_hash == self.tts_service.compute_text_hash(voice_line.text),
                        VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
                    ).order_by(VoiceLineAudio.created_at.desc()).limit(1)
                )
                pending_asset: Optional[VoiceLineAudio] = pending_r.scalar_one_or_none()
                if not pending_asset:
                    pending_r_relaxed = await self.db.execute(
                        select(VoiceLineAudio).where(
                            VoiceLineAudio.voice_line_id == voice_line_id,
                            VoiceLineAudio.voice_id == voice_id,
                            VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
                        ).order_by(VoiceLineAudio.created_at.desc()).limit(1)
                    )
                    pending_asset = pending_r_relaxed.scalar_one_or_none()
            else:
                pending_r = await self.db.execute(
                    select(VoiceLineAudio).where(
                        VoiceLineAudio.voice_line_id == voice_line_id,
                        VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
                    ).order_by(VoiceLineAudio.created_at.desc()).limit(1)
                )
                pending_asset: Optional[VoiceLineAudio] = pending_r.scalar_one_or_none()

            if pending_asset:
                return {"status": "PENDING"}
            raise ValueError("No audio file found for this voice line")

        # Avoid rolling back here before generating signed URL to prevent attribute expiration
        signed_url = await self.tts_service.get_audio_url(asset.storage_path, expires_in)
        if not signed_url:
            raise RuntimeError("Failed to generate audio URL")
        return {"status": "READY", "signed_url": signed_url, "expires_in": expires_in}
