import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.core.logging import console_logger
from app.core.database import AsyncSession
from app.services.audio_preload_service import AudioPreloadService, PreloadedAudio
from app.services.tts_service import TTSService
from app.core.utils.enums import VoiceLineTypeEnum


@dataclass
class CallSession:
    user_id: str
    scenario_id: int
    to_number: str
    from_number: str
    call_id: Optional[str] = None
    call_control_id: Optional[str] = None
    playlist: List[PreloadedAudio] = field(default_factory=list)
    current_index: int = 0


class TelnyxService:
    BASE_URL = "https://api.telnyx.com/v2"
    AUTH_HEADER = {"Authorization": f"Bearer {settings.TELNYX_API_KEY}"}

    # In-memory sessions keyed by call_control_id
    _sessions: Dict[str, CallSession] = {}

    def __init__(self):
        self.tts_service = TTSService()

    async def _ensure_playlist(
        self,
        db_session: AsyncSession,
        user_id: str,
        scenario_id: int,
        preferred_voice_id: Optional[str] = None,
    ) -> List[PreloadedAudio]:
        """
        Ensure audio is preloaded and return ordered playlist for the scenario.
        """
        preload = AudioPreloadService(db_session)
        cache = preload.get_preloaded_audio(user_id, scenario_id)
        if not cache:
            ok, msg, _ = await preload.preload_scenario_audio(user_id, scenario_id, preferred_voice_id)
            if not ok:
                raise RuntimeError(f"Preload failed: {msg}")
            cache = preload.get_preloaded_audio(user_id, scenario_id) or {}

        # Sort all voice lines by order_index
        playlist = sorted(cache.values(), key=lambda a: a.order_index)
        return playlist

    async def initiate_call(
        self,
        db_session: AsyncSession,
        *,
        user_id: str,
        scenario_id: int,
        to_number: str,
        from_number: Optional[str] = None,
        preferred_voice_id: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Create an outbound call via Telnyx Call Control.
        Returns (call_id, call_control_id)
        """
        from_number = from_number or settings.TELNYX_PHONE_NUMBER

        playlist = await self._ensure_playlist(db_session, user_id, scenario_id, preferred_voice_id)
        if not playlist:
            raise RuntimeError("No READY audio found to play.")

        webhook_url = f"{settings.TELNYX_WEBHOOK_BASE_URL}{settings.API_V1_STR}/telnyx/webhook"

        payload = {
            "to": to_number,
            "from": from_number,
            # Either application_id (Call Control App) or connection_id (SIP connection)
            # Prefer Application for Call Control
            "application_id": settings.TELNYX_APPLICATION_ID,
            # Explicit webhook override if needed
            "webhook_url": webhook_url,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/calls",
                headers={**self.AUTH_HEADER, "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()["data"]

        call_id = data["id"]
        call_control_id = data.get("call_control_id") or data.get("call_session_id")
        if not call_control_id:
            raise RuntimeError("Missing call_control_id from Telnyx response.")

        session = CallSession(
            user_id=user_id,
            scenario_id=scenario_id,
            to_number=to_number,
            from_number=from_number,
            call_id=call_id,
            call_control_id=call_control_id,
            playlist=playlist,
            current_index=0,
        )
        self._sessions[call_control_id] = session

        console_logger.info(f"Initiated call {call_id} (control_id={call_control_id}) to {to_number}")
        return call_id, call_control_id

    async def handle_webhook_event(self, event: dict):
        """
        Main webhook event handler for Telnyx Call Control.
        """
        event_type = event.get("data", {}).get("event_type") or event.get("event_type")
        payload = event.get("data", {})
        call_control_id = payload.get("payload", {}).get("call_control_id") or payload.get("call_control_id")
        if not call_control_id:
            console_logger.warning("Webhook without call_control_id; ignoring.")
            return

        session = self._sessions.get(call_control_id)
        if event_type == "call.answered":
            console_logger.info(f"Call answered: {call_control_id}")
            await self._play_current(session)
        elif event_type in ("call.playback.ended", "call.playback.terminated"):
            await self._play_next_or_hangup(session)
        elif event_type in ("call.hangup", "call.ended"):
            console_logger.info(f"Call ended: {call_control_id}")
            self._sessions.pop(call_control_id, None)
        else:
            # Add other events if needed
            pass

    async def _play_current(self, session: CallSession):
        if session.current_index >= len(session.playlist):
            await self.hangup(session.call_control_id)
            return
        item = session.playlist[session.current_index]
        # Get signed URL for Telnyx to pull; mp3 playback is supported by Telnyx
        signed = await self.tts_service.get_audio_url(item.storage_path, expires_in=600)
        if not signed:
            console_logger.error(f"Failed to sign audio for line {item.voice_line_id}, skipping")
            await self._play_next_or_hangup(session)
            return

        await self.playback_start(session.call_control_id, audio_url=signed)

    async def _play_next_or_hangup(self, session: CallSession):
        session.current_index += 1
        if session.current_index < len(session.playlist):
            await self._play_current(session)
        else:
            await self.hangup(session.call_control_id)

    async def playback_start(self, call_control_id: str, *, audio_url: str):
        """
        Ask Telnyx to play an audio file into the call.
        """
        body = {"audio_url": audio_url}
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/calls/{call_control_id}/actions/playback_start",
                headers={**self.AUTH_HEADER, "Content-Type": "application/json"},
                json=body,
            )
            resp.raise_for_status()
        console_logger.debug(f"Playback started on {call_control_id}")

    async def hangup(self, call_control_id: str):
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/calls/{call_control_id}/actions/hangup",
                headers=self.AUTH_HEADER,
            )
            resp.raise_for_status()
        console_logger.info(f"Hung up call {call_control_id}")
        self._sessions.pop(call_control_id, None)

    # Optional: start a media stream fork to our WS endpoint if you want real-time bidirectional audio
    async def fork_start(self, call_control_id: str, session_id: str):
        """
        Tell Telnyx to connect a media stream to our WS endpoint.
        """
        ws_url = f"{settings.TUNNEL_URL}{settings.API_V1_STR}/telnyx/media/{session_id}"
        body = {
            "stream_url": ws_url,
            "audio_format": "audio/pcm;rate=8000",
            "channels": 1,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/calls/{call_control_id}/actions/fork_start",
                headers={**self.AUTH_HEADER, "Content-Type": "application/json"},
                json=body,
            )
            resp.raise_for_status()
        console_logger.info(f"Fork started for {call_control_id} -> {ws_url}")

# Module-level singleton
telnyx_service = TelnyxService()