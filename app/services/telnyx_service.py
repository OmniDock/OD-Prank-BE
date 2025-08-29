import asyncio
from dataclasses import dataclass, field
import secrets
from typing import Dict, List, Optional, Tuple

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
 
from urllib.parse import quote
import asyncio, httpx

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
    conference_name: Optional[str] = None


class TelnyxService:
    BASE_URL = "https://api.telnyx.com/v2"
    AUTH_HEADER = {"Authorization": f"Bearer {settings.TELNYX_API_KEY}"}

    _sessions: Dict[str, CallSession] = {}
    _token_cache: str = None
    _pending_joins: Dict[str, str] = {}
    _sip_to_conf: Dict[str, str] = {}  # sip_username -> conference_name
    _aliases: Dict[str, str] = {}  # inbound leg ccid -> primary session ccid

    def get_session(self, call_control_id: str) -> Optional[CallSession]:
        sess = self._sessions.get(call_control_id)
        if sess:
            return sess
        primary = self._aliases.get(call_control_id)
        if primary:
            return self._sessions.get(primary)
        return None

    def register_webrtc_mapping(self, user_id: str, sip_username: str, conference_name: str) -> None:
        if sip_username and conference_name:
            self._sip_to_conf[sip_username] = conference_name

    async def get_or_create_on_demand_credential(self, user_id: str) -> str:
        """
        Find (by name) or create an On-Demand Telephony Credential under the configured SIP Connection.
        Returns the credential id to be used for JWT minting.
        """
        if not settings.TELNYX_CONNECTION_ID:
            raise RuntimeError("TELNYX_CONNECTION_ID not configured")

        name = f"odprank-{user_id}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Try to find existing credential by name
            r = await client.get(
                f"{self.BASE_URL}/telephony_credentials",
                headers=self.AUTH_HEADER,
            )
            
            if r.status_code >= 400:
                console_logger.error(f"list telephony_credentials error {r.status_code}: {r.text}")
            r.raise_for_status()
            items = (r.json() or {}).get("data") or []
            for item in items:
                if item.get("name") == name:
                    cid = item.get("id")
                    sip_username = item.get("sip_username")
                    if cid:
                        return cid, sip_username

            # Create a new credential
            payload = {
                "connection_id": settings.TELNYX_CONNECTION_ID,
                "name": name,
            }
            r2 = await client.post(
                f"{self.BASE_URL}/telephony_credentials",
                headers={**self.AUTH_HEADER, "Content-Type": "application/json"},
                json=payload,
            )
            if r2.status_code >= 400:
                console_logger.error(f"create telephony_credential error {r2.status_code}: {r2.text}")
            r2.raise_for_status()
            cid = ((r2.json() or {}).get("data") or {}).get("id")
            sip_username = ((r2.json() or {}).get("data") or {}).get("sip_username")

            console_logger.info(f"created telephony_credential: {r2.json()}")

            if not cid:
                raise RuntimeError("Created telephony credential but response missing id")
            return cid, sip_username
        
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

        # per-call secret conference name (unguessable)
        secret_conf = f"{secrets.token_urlsafe(64)}"

        payload = {
            "to": to_number,
            "from": from_number,
            "connection_id": settings.TELNYX_APPLICATION_ID,
            "webhook_url": f"{settings.TELNYX_WEBHOOK_BASE_URL}{settings.API_V1_STR}/telnyx/webhook",
            "conference_config": {
                "conference_name": secret_conf,
                "start_conference_on_enter": True
            }
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/calls",
                headers={**self.AUTH_HEADER, "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()['data']
            #console_logger.info(f"Telnyx response: {data}")

        call_leg_id = data["call_leg_id"]
        call_control_id = data.get("call_control_id")
        call_session_id = data.get("call_session_id")

        console_logger.info(f"Call Initiated: {data}")

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
            conference_name=secret_conf,
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

        p = payload.get("payload", {}) or {}

        if not call_control_id:
            console_logger.warning("Webhook without call_control_id; ignoring.")
            return

        session = self._sessions.get(call_control_id)

        # Try to extract conference name from client_state (base64)
        conf_from_state: Optional[str] = None
        cs_b64 = p.get("client_state") or payload.get("client_state")
        if cs_b64:
            try:
                conf_from_state = base64.b64decode(cs_b64).decode("utf-8")
            except Exception:
                conf_from_state = None

        # if event_type == "call.initiated":
        #     p = payload.get("payload", {}) or {}
        #     direction = (p.get("direction") or "").lower()
        #     ccid = p.get("call_control_id")

        #     # Nur INBOUND/INCOMING-Legs behandeln
        #     if direction not in ("incoming", "inbound"):
        #         console_logger.info(f"Skip non-inbound leg {ccid} dir={direction}")
        #         return

        #     # 1) Konferenzname aus Header holen (empfohlen)
        #     headers_list = p.get("custom_headers") or []
        #     headers = { (h.get("name") or "").lower(): (h.get("value") or "") for h in headers_list }
        #     conf = headers.get("x-conference-name")

        #     # 2) Optional: Wenn du per SIP-URI dialst, userpart als Fallback:
        #     # to_uri = p.get("to") or ""
        #     # if not conf and isinstance(to_uri, str) and to_uri.startswith("sip:"):
        #     #     conf = to_uri.split("sip:", 1)[1].split("@", 1)[0]

        #     # 3) Optionaler weiterer Fallback: serverseitiges Mapping (z. B. pro User/Session)
        #     # if not conf:
        #     #     conf = self.resolve_conf_for_user(...)

        #     if not conf:
        #         console_logger.warning(f"Inbound {ccid} ohne Conference-Name; headers={headers}")
        #         return

        #     console_logger.info(f"Inbound {ccid} -> join conference {conf}")
        #     try:
        #         await self.join_conference(ccid, conf)  # impliziert Answer
        #     except Exception as e:
        #         console_logger.error(f"conference_join error for {ccid}: {e}")
        #     return
        if event_type == "call.initiated":
            p = (payload.get("payload") or {})
            if (p.get("direction","").lower() in ("incoming","inbound")):
                ccid = p["call_control_id"]
                hdrs = { (h.get("name") or "").lower(): (h.get("value") or "") for h in (p.get("custom_headers") or []) }
                conf = hdrs.get("x-conference-name")
                if not conf:
                    console_logger.warning(f"Inbound {ccid} without X-Conference-Name"); return

                # Map inbound WebRTC leg to the existing session by conference
                try:
                    primary = next((s for s in self._sessions.values() if s.conference_name == conf), None)
                    if primary:
                        self._aliases[ccid] = primary.call_control_id
                except Exception:
                    pass

                console_logger.info(f"Inbound {ccid} -> answer then join {conf}")
                # 1) answer
                await self.answer_with_retry(ccid)
                # 2) join
                await self.join_conference_by_name(ccid, conf, mute=True)
                # 3) start Media Stream on the inbound WebRTC leg too
                try:
                    await self.fork_start(ccid)
                except Exception as e:
                    console_logger.error(f"fork_start error for inbound {ccid}: {e}")
            return

        if event_type == "call.answered":
            dir_str = (p.get("direction") or "").lower()
            frm = p.get("from") or ""
            to = p.get("to") or ""
            console_logger.info(f"Call answered: {call_control_id} (dir={dir_str}, from={frm}, to={to})")
                
        elif event_type in ("call.hangup", "call.ended"):
            console_logger.info(f"Call ended: {call_control_id}")
            # Cleanup
            self._pending_joins.pop(call_control_id, None)
            self._sessions.pop(call_control_id, None)

        # Join any pending leg when it gets answered (works for inbound/outbound WebRTC)
        if event_type == "call.answered":
            # If we have a pending target conference for this leg, join now
            pending = self._pending_joins.pop(call_control_id, None)
            if pending:
                console_logger.info(f"Joining leg {call_control_id} to conference {pending}")
                try:
                    await self.join_conference(call_control_id, pending)
                except Exception as e:
                    console_logger.error(f"conference_join error for {call_control_id}: {e}")
                return
            
            # Fallback: if client_state was present but we didn't set pending (e.g., non-inbound direction)
            if conf_from_state:
                console_logger.info(f"Joining leg {call_control_id} to conference {conf_from_state} (fallback)")
                try:
                    await self.join_conference(call_control_id, conf_from_state)
                except Exception as e:
                    console_logger.error(f"conference_join error for {call_control_id}: {e}")
                return
            
            if session and session.conference_name:
                # Outbound PSTN leg we created; start Media Stream only. Conference_config handles joining.
                try:
                    await self.fork_start(call_control_id)
                except Exception as e:
                    console_logger.error(f"fork_start error for {call_control_id}: {e}")
                return



    async def fork_start(self, call_control_id: str):
        base = settings.TUNNEL_URL.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{base}{settings.API_V1_STR}/telnyx/media/{call_control_id}"

        body = {
            "stream_url": ws_url,
            "stream_track": "both_tracks",
            "stream_codec": "PCMU",
            "stream_bidirectional_mode": "rtp",
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


    async def answer_call(self, call_control_id: str):
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{self.BASE_URL}/calls/{call_control_id}/actions/answer",
                headers={**self.AUTH_HEADER, "Content-Type": "application/json"},
            )
            if r.status_code >= 400:
                console_logger.error(f"answer action error {r.status_code}: {r.text}")
            r.raise_for_status()





    async def answer_with_retry(self, ccid: str, retries: int = 4):
        ccid_path = quote(ccid, safe="")
        url = f"{self.BASE_URL}/calls/{ccid_path}/actions/answer"
        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(1, retries+1):
                r = await client.post(url, headers={**self.AUTH_HEADER, "Content-Type": "application/json"})
                if r.status_code == 404 and attempt < retries:
                    await asyncio.sleep(0.15 * attempt)  # 150ms, 300ms, ...
                    continue
                r.raise_for_status()
                return

    async def join_conference_by_name(self, inbound_ccid: str, conf: str, retries: int = 5, mute: bool = False):
        conf_path = quote(conf, safe="")
        url = f"{self.BASE_URL}/conferences/{conf_path}/actions/join"
        body = {"call_control_id": inbound_ccid, "start_conference_on_enter": True, "mute": mute}
        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(1, retries+1):
                r = await client.post(url, headers={**self.AUTH_HEADER, "Content-Type": "application/json"}, json=body)
                if r.status_code in (404, 422) and attempt < retries:
                    # 404: leg/conference not ready; 422: not answered yet -> give core a moment
                    await asyncio.sleep(0.15 * attempt)
                    continue
                r.raise_for_status()
                return

    # No retry helper; rely on single join attempt when leg is answered

    async def stream_playlist_over_ws(self, ws, session: CallSession, stream_id: Optional[str] = None):
        """
        Stream audio to Telnyx and broadcast BOTH directions to monitors.
        """
        try:
            if not session.playlist:
                return

            # Use only one audio file
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
                    frame = {
                        "event": "media",
                        "media": {
                            "payload": chunk_b64
                        }
                    }
                    if stream_id:
                        frame["stream_id"] = stream_id

                    await ws.send_text(json.dumps(frame))                                        
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