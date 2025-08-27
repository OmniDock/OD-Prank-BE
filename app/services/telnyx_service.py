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
    ) -> Tuple[str, str, str]:
        """
        Create an outbound call via Telnyx Call Control.
        Returns (call_leg_id, call_control_id, call_session_id)
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
            if session:
                await self.fork_start(call_control_id)
        elif event_type in ("call.hangup", "call.ended"):
            console_logger.info(f"Call ended: {call_control_id}")
            self._sessions.pop(call_control_id, None)

    async def fork_start(self, call_control_id: str):
        base = settings.TUNNEL_URL.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{base}{settings.API_V1_STR}/telnyx/media/{call_control_id}"

        body = {
            "stream_url": ws_url,
            "stream_track": "inbound_track",
            "stream_codec": "PCMU",
            "stream_bidirectional_mode": "mp3",
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

    async def stream_playlist_over_ws(self, ws, session: CallSession):
        """
        Stream audio to Telnyx and broadcast BOTH directions to monitors.
        """
        try:
            if not session.playlist:
                return

            # Use first audio file
            item = session.playlist[0]
            
            # Convert to 8kHz μ-law
            segment = AudioSegment.from_file(io.BytesIO(item.audio_data), format="mp3")
            segment = segment.set_frame_rate(8000).set_channels(1).set_sample_width(2).normalize()
            
            # Use 160-sample chunks (20ms at 8kHz) - standard for telephony
            chunk_ms = 20
            
            # Convert entire audio to μ-law chunks
            chunks = []
            for i in range(0, len(segment), chunk_ms):
                chunk = segment[i:i+chunk_ms]
                if len(chunk) < chunk_ms:
                    # Pad last chunk with silence
                    chunk = chunk + AudioSegment.silent(duration=chunk_ms - len(chunk))
                pcm = chunk.raw_data
                ulaw = audioop.lin2ulaw(pcm, 2)
                chunks.append(base64.b64encode(ulaw).decode('ascii'))

            # Stream with precise timing
            start_time = asyncio.get_event_loop().time()
            total_chunks_sent = 0
            
            while self.get_session(session.call_control_id):
                for chunk_b64 in chunks:
                    if not self.get_session(session.call_control_id):
                        return
                    
                    # Send to Telnyx
                    await ws.send_text(json.dumps({
                        "event": "media",
                        "media": {
                            "track": "outbound",
                            "payload": chunk_b64
                        }
                    }))
                    
                    # Broadcast outbound audio to monitors
                    await self.broadcast(session.call_control_id, "outbound", chunk_b64)
                    
                    # Precise timing - account for total chunks sent across loops
                    total_chunks_sent += 1
                    next_time = start_time + (total_chunks_sent * 0.02)  # 20ms per chunk
                    sleep_time = next_time - asyncio.get_event_loop().time()
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                        
        except Exception as e:
            console_logger.error(f"Stream error: {e}")

# Module-level singleton
telnyx_service = TelnyxService()