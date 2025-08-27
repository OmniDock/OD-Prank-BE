import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set

import httpx
import base64
import io
import json
import audioop
from pydub import AudioSegment

from app.core.config import settings
from app.core.logging import console_logger
from app.core.database import AsyncSession
from app.services.audio_preload_service import AudioPreloadService, PreloadedAudio
from fastapi import WebSocket


@dataclass
class CallSession:
    user_id: str
    scenario_id: int
    to_number: str
    from_number: str
    call_leg_id: Optional[str] = None
    call_control_id: Optional[str] = None
    call_session_id: Optional[str] = None
    playlist: List[PreloadedAudio] = field(default_factory=list)
    current_index: int = 0
    stream_mode: bool = True


class TelnyxService:
    BASE_URL = "https://api.telnyx.com/v2"
    AUTH_HEADER = {"Authorization": f"Bearer {settings.TELNYX_API_KEY}"}

    # In-memory sessions keyed by call_control_id
    _sessions: Dict[str, CallSession] = {}
    _monitors: Dict[str, Set[WebSocket]] = {}

    def register_monitor(self, call_control_id: str, ws: WebSocket) -> None:
        self._monitors.setdefault(call_control_id, set()).add(ws)

    def unregister_monitor(self, call_control_id: str, ws: WebSocket) -> None:
        if call_control_id in self._monitors:
            self._monitors[call_control_id].discard(ws)
            if not self._monitors[call_control_id]:
                del self._monitors[call_control_id]

    async def broadcast(self, call_control_id: str, direction: str, payload_b64: str) -> None:
        """Broadcast base64 media payload to any monitor websockets for this call."""
        for ws in list(self._monitors.get(call_control_id, [])):
            try:
                await ws.send_json({
                    "event": "media",
                    "direction": direction,
                    "codec": "PCMU",
                    "rate": 8000,
                    "payload": payload_b64,
                })
            except Exception:
                self.unregister_monitor(call_control_id, ws)

    def get_session(self, call_control_id: str) -> Optional[CallSession]:
        return self._sessions.get(call_control_id)
    
    def __init__(self):
        pass

    async def _ensure_playlist(
        self,
        db_session: AsyncSession,
        user_id: str,
        scenario_id: int,
    ) -> List[PreloadedAudio]:
        """
        Ensure audio is preloaded and return ordered playlist for the scenario.
        """
        preload = AudioPreloadService(db_session)
        cache = preload.get_preloaded_audio(user_id, scenario_id)
        if not cache:
            ok, msg, _ = await preload.preload_scenario_audio(user_id, scenario_id)
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
    ) -> Tuple[str, str]:
        """
        Create an outbound call via Telnyx Call Control.
        Returns (call_id, call_control_id)
        """
        from_number = settings.TELNYX_PHONE_NUMBER

        playlist = await self._ensure_playlist(db_session, user_id, scenario_id)
        if not playlist:
            raise RuntimeError("No READY audio found to play.")

        payload = {
            "to": to_number,
            "from": from_number,
            "connection_id": settings.TELNYX_APPLICATION_ID, 
            "webhook_url": f"{settings.TELNYX_WEBHOOK_BASE_URL}{settings.API_V1_STR}/telnyx/webhook"
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/calls",
                headers={**self.AUTH_HEADER, "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()['data']
            console_logger.info(f"Telnyx response: {data}")

        call_leg_id = data["call_leg_id"]
        call_control_id = data.get("call_control_id")
        call_session_id = data.get("call_session_id")

        if not call_control_id:
            raise RuntimeError("Missing call_control_id from Telnyx response.")

        session = CallSession(
            user_id=user_id,
            scenario_id=scenario_id,
            to_number=to_number,
            from_number=from_number,
            call_leg_id=call_leg_id,
            call_control_id=call_control_id,
            call_session_id=call_session_id,
            playlist=playlist,
            current_index=0,
        )
        self._sessions[call_control_id] = session

        console_logger.info(f"Initiated call {call_leg_id} (control_id={call_control_id}) to {to_number}")
        return call_leg_id, call_control_id, call_session_id

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
            if session and session.stream_mode:
                await self.fork_start(call_control_id, session_id=call_control_id)
        elif event_type in ("call.hangup", "call.ended"):
            console_logger.info(f"Call ended: {call_control_id}")
            self._sessions.pop(call_control_id, None)
        else:
            # Add other events if needed
            pass

    # Optional: start a media stream fork to our WS endpoint if you want real-time bidirectional audio
    async def fork_start(self, call_control_id: str, session_id: str):
        """
        Tell Telnyx to connect a media stream to our WS endpoint.
        """
        # Build a WSS URL (convert http/https to ws/wss)
        base = settings.TUNNEL_URL.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{base}{settings.API_V1_STR}/telnyx/media/{call_control_id}"

        body = {
            "stream_url": ws_url,
            "stream_track": "both_tracks",
            "stream_bidirectional_mode": "rtp",
            "stream_bidirectional_codec": "PCMU"
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/calls/{call_control_id}/actions/streaming_start",
                headers={**self.AUTH_HEADER, "Content-Type": "application/json"},
                json=body,
            )
            if resp.status_code >= 400:
                console_logger.error(f"Telnyx streaming_start error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
        console_logger.info(f"Fork started for {call_control_id} -> {ws_url}")

    async def stream_playlist_over_ws(self, ws, session: CallSession, stream_id: str):
        """
        Stream the first preloaded sound to Telnyx WS as PCMU (8kHz) frames.
        Loops continuously until Telnyx hangs up (WS closes) or we drop the session.
        """
        try:
            if not session.playlist:
                return

            # Use precomputed μ-law chunks if available, else compute on the fly with 200ms windows
            item = session.playlist[0]

            if getattr(item, "ulaw_chunks_b64", None):
                chunks_b64 = item.ulaw_chunks_b64 or []
                chunk_ms = item.ulaw_chunk_ms or 200
            else:
                # Fallback: precompute quickly from in-memory MP3
                segment = AudioSegment.from_file(io.BytesIO(item.audio_data), format="mp3")
                segment = segment.set_frame_rate(8000).set_channels(1).set_sample_width(2)
                chunk_ms = 200
                chunks_b64: List[str] = []
                total_ms = len(segment)
                for start_ms in range(0, total_ms, chunk_ms):
                    chunk = segment[start_ms:start_ms + chunk_ms]
                    pcm16 = chunk.raw_data
                    ulaw = audioop.lin2ulaw(pcm16, 2)
                    chunks_b64.append(base64.b64encode(ulaw).decode("ascii"))

            # Loop until session removed (hangup) or WS closed
            while self.get_session(session.call_control_id) is not None:
                for payload in chunks_b64:
                    if self.get_session(session.call_control_id) is None:
                        return
                    await ws.send_text(json.dumps({
                        "event": "media",
                        "stream_id": stream_id,
                        "media": {"payload": payload}
                    }))
                    await asyncio.sleep((chunk_ms) / 1000.0)
        except Exception as e:
            console_logger.error(f"Error streaming audio over WS: {e}")

# Module-level singleton
telnyx_service = TelnyxService()