from typing import List, Dict, Tuple, Optional
from sqlalchemy import select, func, and_
from app.core.database import AsyncSession
from app.core.auth import AuthUser
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.voice_line_repository import VoiceLineRepository
from app.models.voice_line_audio import VoiceLineAudio
from app.models.voice_line import VoiceLine
from app.services.tts_service import TTSService
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

    async def request_tts_single(self, user: AuthUser, voice_line_id: int, voice_id: str) -> Dict:
        """Prepare or reuse TTS for a single voice line.
        Returns a dict with either 'ready', 'in_progress', or 'created_pending' and payloads.
        """
        voice_line = await self.voice_line_repo.get_voice_line_by_id_with_user_check(voice_line_id, user.id_str)
        if not voice_line:
            raise ValueError("Voice line not found or access denied")

        voice_settings = self.tts_service.default_voice_settings()
        model = ElevenLabsModelEnum.ELEVEN_TTV_V3
        content_hash = self.tts_service.compute_content_hash(voice_line.text, voice_id, model, voice_settings)

        # Reuse READY
        r = await self.db.execute(
            select(VoiceLineAudio).where(
                VoiceLineAudio.voice_line_id == voice_line_id,
                VoiceLineAudio.content_hash == content_hash,
                VoiceLineAudio.status == VoiceLineAudioStatusEnum.READY,
            ).limit(1)
        )
        existing: Optional[VoiceLineAudio] = r.scalar_one_or_none()
        if existing and existing.storage_path:
            signed_url = await self.tts_service.get_audio_url(existing.storage_path)
            return {
                "status": "ready",
                "voice_line_id": voice_line_id,
                "signed_url": signed_url,
                "storage_path": existing.storage_path,
            }

        # In progress check
        inprog_r = await self.db.execute(
            select(VoiceLineAudio).where(
                VoiceLineAudio.voice_line_id == voice_line_id,
                VoiceLineAudio.content_hash == content_hash,
                VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
            ).limit(1)
        )
        in_progress = inprog_r.scalar_one_or_none()
        if in_progress:
            return {"status": "in_progress", "voice_line_id": voice_line_id}

        # Create PENDING
        processing_asset = VoiceLineAudio(
            voice_line_id=voice_line_id,
            voice_id=voice_id,
            model_id=ElevenLabsModelEnum.ELEVEN_TTV_V3,
            voice_settings=voice_settings,
            storage_path=None,
            duration_ms=None,
            size_bytes=None,
            text_hash=self.tts_service.compute_text_hash(voice_line.text),
            settings_hash=self.tts_service.compute_settings_hash(voice_id, model, voice_settings),
            content_hash=content_hash,
            status=VoiceLineAudioStatusEnum.PENDING,
            error=None,
        )
        self.db.add(processing_asset)
        await self.db.commit()

        # Return payload for background job scheduling
        return {
            "status": "created_pending",
            "voice_line_id": voice_line_id,
            "background_payload": {
                "voice_line_id": voice_line_id,
                "user_id": user.id_str,
                "text": voice_line.text,
                "voice_id": voice_id,
                "model": model,
                "voice_settings": voice_settings,
                "content_hash": content_hash,
            },
        }

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

        for vl in voice_lines:
            try:
                prepared = await self.request_tts_single(user, vl.id, selected_default_voice_id)
                if prepared["status"] == "ready":
                    results.append({
                        "voice_line_id": vl.id,
                        "success": True,
                        "signed_url": prepared.get("signed_url"),
                        "storage_path": prepared.get("storage_path"),
                        "error_message": None,
                    })
                elif prepared["status"] == "in_progress":
                    results.append({
                        "voice_line_id": vl.id,
                        "success": False,
                        "signed_url": None,
                        "storage_path": None,
                        "error_message": "Audio generation already in progress",
                    })
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
            except Exception as e:
                results.append({
                    "voice_line_id": vl.id,
                    "success": False,
                    "signed_url": None,
                    "storage_path": None,
                    "error_message": f"Generation failed: {str(e)}",
                })

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

        signed_url = await self.tts_service.get_audio_url(asset.storage_path, expires_in)
        if not signed_url:
            raise RuntimeError("Failed to generate audio URL")
        return {"status": "READY", "signed_url": signed_url, "expires_in": expires_in}
