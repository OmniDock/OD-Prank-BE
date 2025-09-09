import asyncio 
import json 
from typing import Dict
from fastapi import WebSocket, WebSocketDisconnect

from typing import Tuple

from app.core.database import AsyncSession 
from app.core.logging import console_logger 
from app.services.telnyx.client import TelnyxHTTPClient 
from app.services.telnyx.sessions import TelnyxSessionService, CallSession 
from app.services.audio_preload_service import AudioPreloadService 
from app.services.tts_service import TTSService
from app.services.cache_service import CacheService
from app.models.call_log import CallLog
from app.models.scenario import Scenario
from app.models.blacklist import Blacklist
from sqlalchemy import select, func
from fastapi import HTTPException
import datetime
import pytz
import base64
import wave
from supabase import create_client
from app.core.config import settings
import io

# Preload background noise into memory at startup
background_noise_pcm = None

async def preload_background_noise_from_supabase(storage_path="office.wav"):
    global background_noise_pcm
    try:
        console_logger.info(f"Preloading background noise from Supabase: {storage_path} length:")
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        res = client.storage.from_("ringtones").download(storage_path)
        if hasattr(res, 'data'):
            wav_bytes = res.data
        else:
            wav_bytes = res
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            # Accept only μ-law (format 7), 8kHz, mono, 8-bit
            if wf.getframerate() != 8000 or wf.getnchannels() != 1 or wf.getsampwidth() != 1 or wf.getcomptype() != 'NONE':
                raise ValueError("Background noise WAV must be 8kHz, mono, 8-bit (μ-law, format 7, uncompressed)")
            if wf.getparams().comptype == 'NONE' and wf.getparams().sampwidth == 1 and wf.getparams().nchannels == 1 and wf.getparams().framerate == 8000 and wf.getparams().nframes > 0:
                # This is likely μ-law, but wave module does not decode it; just read the bytes
                background_noise_pcm = wf.readframes(wf.getnframes())
                # These are μ-law bytes, ready to stream to Telnyx
            else:
                raise ValueError(f"Unsupported WAV format: framerate={wf.getframerate()}, channels={wf.getnchannels()}, sampwidth={wf.getsampwidth()}, comptype={wf.getcomptype()}")
            console_logger.info(f"Loaded background noise from Supabase: {storage_path} length: {len(background_noise_pcm)} (μ-law bytes)")
    except Exception as e:
        console_logger.error(f"Failed to preload background noise from Supabase: {e}")


class TelnyxHandler: 

    _session_service = TelnyxSessionService()
    _client = TelnyxHTTPClient()
    _active_playbacks_tasks: Dict[str, asyncio.Task] = {}

    def __init__(self):
        self.logger = console_logger 

    async def initiate_call(
        self,
        db_session: AsyncSession,
        user_id: str,
        scenario_id: int,
        to_number: str,
        *args, **kwargs
    ) -> Tuple[str, str, str, str]:
        # --- Restriction Checks ---
        # 1. Scenario ownership/public
        scenario = await db_session.get(Scenario, scenario_id)
        if not scenario or (str(scenario.user_id) != user_id and not getattr(scenario, "is_public", False)):
            # Frontend should display this error message
            raise HTTPException(status_code=403, detail="You do not have permission to use this scenario.")
        # 2. Blacklist check
        result = await db_session.execute(select(Blacklist).where(Blacklist.phone_number == to_number))
        if result.scalar():
            raise HTTPException(status_code=403, detail="This phone number is blacklisted.")
        # 3. Rate limit (max 10 calls in 24h)
        since = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
        count_result = await db_session.execute(
            select(func.count()).select_from(CallLog).where(
                CallLog.user_id == user_id,
                CallLog.call_timestamp >= since
            )
        )
        if count_result.scalar() >= 10:
            raise HTTPException(status_code=429, detail="Call limit exceeded for the last 24 hours.")
        # 4. Time-of-day check (no calls after 22:00 Europe/Berlin)
        now = datetime.datetime.now(pytz.timezone("Europe/Berlin"))
        if now.hour >= 22:
            raise HTTPException(status_code=403, detail="Calls are not allowed after 22:00.")
        # --- End Restriction Checks ---
        
        # PRELOADING AUDIO (TO BE EXCHANGED LATER)
        audio_service = AudioPreloadService(db_session)
        success, message = await audio_service.preload_scenario_audio(user_id, scenario_id)
        if not success: 
            raise HTTPException(status_code=500, detail=f"Failed to preload audio for scenario {scenario_id}: {message}")
        
        # INITIATING THE CALL 
        call_leg_id, call_control_id, call_session_id, conference_name = await self._client.initiate_call(to_number)
        preloaded_audio = await audio_service.get_preloaded_audio(user_id, scenario_id)

        session = CallSession(
            user_id=str(user_id),
            scenario_id=scenario_id,
            to_number=to_number,
            from_number=self._client.FROM_NUMBER,
            outbound_call_leg_id=call_leg_id,
            outbound_call_control_id=call_control_id,
            outbound_call_session_id=call_session_id,
            conference_name=conference_name,
            voice_line_audios = preloaded_audio
        )
        await self._session_service.add_conference_session(session)
        await self._session_service.add_ccid_to_conference(conference_name, call_control_id)

        self.logger.info(f"Initiated call {call_leg_id} (control_id={call_control_id}) to {to_number}")
        # --- Log the call ---
        call_log = CallLog(
            user_id=user_id,
            to_number=to_number,
            scenario_id=scenario_id,
            call_timestamp=datetime.datetime.utcnow(),
            call_status="initiated",
            metadata=None
        )
        db_session.add(call_log)
        await db_session.commit()
        return call_leg_id, call_control_id, call_session_id, conference_name
    

    async def get_webrtc_token(self, user_id: str):
        cred_id = await self._client.get_or_create_on_demand_credential(user_id)
        token = await self._client.mint_webrtc_token(cred_id)   
        return token




    async def handle_webhook_event(self, event: dict):
        """
        Handle a webhook event from Telnyx.
        """
        data = event.get("data", {})
        event_type = data.get("event_type")
        payload = data.get("payload", {})
        call_control_id = payload.get("call_control_id")

        self.logger.info(f"Telnyx webhook event: {event_type}")

        if not call_control_id:
            console_logger.warning("Webhook without call_control_id; ignoring.")
            return

        if event_type == "call.initiated":
            # Differentiate between inbound and outbound calls. 
            direction = payload.get("direction")
            if direction == "outgoing":
                # Outbound Calls from the API are answered by the called person.
                return 
            elif direction == "incoming":

                existing_conference = await self._session_service.get_conference_name_by_ccid(call_control_id)
                if existing_conference:
                    console_logger.debug(f"Already processed incoming call {call_control_id}, skipping duplicate webhook")
                    return
                
                # Inbound Calls from Browsers need to be answered and joined to the conference. 
                custom_headers = { (h.get("name") or "").lower(): (h.get("value") or "") for h in (payload.get("custom_headers") or []) }
                conference_name = custom_headers.get("x-conference-name")
                if conference_name:

                    session = await self._session_service.get_conference_session(conference_name)
                    if not session:
                        raise RuntimeError(f"No session found for conference {conference_name} (Incoming Call)")
                    
                    session.webrtc_call_control_id = call_control_id
                    await self._session_service.add_conference_session(session)
                    await self._session_service.add_ccid_to_conference(conference_name, call_control_id)
                    await self._client.answer_with_retry(call_control_id)
                    await self._client.join_conference_by_name(call_control_id, conference_name, mute=True)
                    # await self._client.media_stream_start(call_control_id)

                else:
                    self.logger.warning(f"(call.initiated) (outgoing) No conference name found in custom headers")
                    return
            else:
                return 

        elif event_type == "call.answered":
            if call_control_id:
                console_logger.warning(f"(call.answered) Starting media stream for call control id {call_control_id}")
                await self._client.start_media_stream(call_control_id)
            else:
                self.logger.warning(f"(call.answered) No call control id found for call")
                return
            pass

        # elif event_type == "conference.participant.joined":
        #     if call_control_id:
        #         console_logger.warning(f"(conference.participant.joined) Starting media stream for call control id {call_control_id}")
        #         await self._client.start_media_stream(call_control_id)
        #     else:
        #         self.logger.warning(f"(conference.participant.joined) No call control id found for call")
        #         return
        #     pass

        elif event_type == "call.hangup":
            conference_name = await self._session_service.get_conference_name_by_ccid(call_control_id)
            if not conference_name:
                self.logger.warning(f"(call.hangup) No conference name found for call control id {call_control_id}")
                return
            session = await self._session_service.get_conference_session(conference_name)
            if not session:
                self.logger.warning(f"(call.hangup) No session found for conference name {conference_name}")
                return

            outbound_ccid = session.outbound_call_control_id
            if outbound_ccid and outbound_ccid != call_control_id:
                await self._client.hangup_call(outbound_ccid)

            inbound_ccid = session.webrtc_call_control_id
            if inbound_ccid and inbound_ccid != call_control_id:
                await self._client.hangup_call(inbound_ccid)

            await self._session_service.remove_conference_session(conference_name)
            # Clear PSTN joined flag on hangup
            try:
                cache = await CacheService.get_global()
                await cache.delete(f"conf:{conference_name}:pstn_joined")
            except Exception:
                pass

        elif event_type in ("conference.participant.joined", "conference.participant.left", "conference.participant.removed"):
            # Track PSTN leg presence for UI status
            conference_name = event.get("data", {}).get("payload", {}).get("conference_name")
            if not conference_name:
                # Fallback via ccid mapping
                conference_name = await self._session_service.get_conference_name_by_ccid(call_control_id)
            if not conference_name:
                return
            session = await self._session_service.get_conference_session(conference_name)
            if not session:
                return
            is_pstn_leg = session.outbound_call_control_id and session.outbound_call_control_id == call_control_id
            if not is_pstn_leg:
                return
            try:
                cache = await CacheService.get_global()
                if event_type == "conference.participant.joined":
                    await cache.set(f"conf:{conference_name}:pstn_joined", "1", ttl=3600)
                else:
                    await cache.delete(f"conf:{conference_name}:pstn_joined")
            except Exception:
                pass



    async def _ensure_background_noise_loaded(self):
        global background_noise_pcm
        if background_noise_pcm is None:
            await preload_background_noise_from_supabase()

    async def _stream_background_noise(self, ws: WebSocket, stop_event: asyncio.Event):
        global background_noise_pcm
        await self._ensure_background_noise_loaded()
        if background_noise_pcm is None:
            console_logger.error("Background noise not loaded in memory.")
            return
        chunk_size = 160  # 20ms of 8kHz 8-bit mono μ-law = 160 bytes
        console_logger.warning(f"Streaming background noise to Telnyx: {len(background_noise_pcm)}")
        try:
            while not stop_event.is_set():
                pos = 0
                while pos < len(background_noise_pcm) and not stop_event.is_set():
                    chunk = background_noise_pcm[pos:pos+chunk_size]
                    payload = base64.b64encode(chunk).decode('ascii')
                    msg = json.dumps({
                        "event": "media",
                        "media": {"payload": payload}
                    })
                    try:
                        await ws.send_text(msg)
                    except Exception as e:
                        console_logger.error(f"Failed to send background noise: {e}")
                        return
                    await asyncio.sleep(0.02)  # 20ms per chunk
                    pos += chunk_size
        except Exception as e:
            console_logger.error(f"Background noise streaming error: {e}")

    async def handle_media_ws(self, ws: WebSocket, call_control_id: str):
        await ws.accept()

        conference_name = await self._session_service.get_conference_name_by_ccid(call_control_id)
        session = await self._session_service.get_conference_session(conference_name)
        if not session:
            await ws.close()
            console_logger.error(f"(xyz) No session found for call control id {call_control_id}")
            return

        console_logger.warning(f"(xyz) Adding WebSocket for call control id {call_control_id}")
        
        self._session_service.add_websocket(call_control_id, ws)
        stop_event = asyncio.Event()

        console_logger.warning(f"(xyz) Creating background noise task for call control id {call_control_id}")
        bg_task = asyncio.create_task(self._stream_background_noise(ws, stop_event))
        try:
            while True:
                inbound_msg = await ws.receive_text()
                inbound = json.loads(inbound_msg)
                if inbound.get("event") in ("stop", "streaming_stopped"):
                    break
        except WebSocketDisconnect:
            pass
        except Exception as e:
            console_logger.error(f"Media WS error: {e}")
        finally:
            stop_event.set()
            await bg_task
            self._session_service.remove_websocket(call_control_id, ws)
            await ws.close()


    async def play_voice_line(self, user_id: str, conference_name: str, voice_line_id: int):
        session = await self._session_service.get_conference_session(conference_name)
        if not session:
            raise RuntimeError(f"No session found for conference {conference_name}")
        if str(session.user_id) != str(user_id):
            raise RuntimeError(f"User {user_id} does not have access to conference {conference_name}")

        # Ensure voice line exists in session
        if not session.voice_line_audios or voice_line_id not in session.voice_line_audios:
            raise RuntimeError(f"Voice line {voice_line_id} not found in session")

        # Stop any active voice line playback first
        # await self.stop_voice_line(user_id, conference_name)

        audio = session.voice_line_audios[voice_line_id]

        # Use pre-cached signed URL if available, otherwise generate new one
        signed_url = audio.signed_url
        if not signed_url:
            tts = TTSService()
            signed_url = await tts.get_audio_url(audio.storage_path, expires_in=1800)
            if not signed_url:
                raise RuntimeError("Failed to create signed URL for audio")

        # Prefer conference-level playback so all participants hear it
        try:
            await self._client.conference_play(conference_name, signed_url)
        except Exception:
            # Fallback: play on each leg
            ccids = await self._session_service.get_ccids_by_conference(conference_name)
            if not ccids:
                raise RuntimeError(f"No call legs found for conference {conference_name}")
            await asyncio.gather(*[
                self._client.playback_start(ccid, signed_url)
            for ccid in ccids])
        return

    async def stop_voice_line(self, user_id: str, conference_name: str):
        """
        Stop any active voice line playback for a conference.
        """
        session = await self._session_service.get_conference_session(conference_name)
        if session and str(session.user_id) != user_id:
            raise RuntimeError(f"User {user_id} does not have access to conference {conference_name}")

        # Try to stop conference-level playback; fallback per leg
        try:
            await self._client.conference_stop(conference_name)
            return True
        except Exception:
            ccids = await self._session_service.get_ccids_by_conference(conference_name)
            if not ccids:
                return False
            await asyncio.gather(*[self._client.playback_stop(ccid) for ccid in ccids], return_exceptions=True)
            return True

    async def hangup_call(self, user_id: str, conference_name: str):
        """
        Hangup all calls in a conference.
        """
        # CHECK IF SESSION EXISTS 
        session = await self._session_service.get_conference_session(conference_name)
        if not session:
            raise RuntimeError(f"No session found for conference {conference_name}")
        
        if str(session.user_id) != user_id:
            raise RuntimeError(f"User {user_id} does not have access to conference {conference_name}")
        
        # Stop any active voice line playback first
        await self.stop_voice_line(user_id, conference_name)
        
        # Get all call control IDs in this conference
        ccids = await self._session_service.get_ccids_by_conference(conference_name)
        
        # Hangup all calls in the conference
        hangup_tasks = []
        for ccid in ccids:
            hangup_tasks.append(self._client.hangup_call(ccid))
        
        if hangup_tasks:
            await asyncio.gather(*hangup_tasks, return_exceptions=True)
        
        # Clean up sessions
        for ccid in ccids:
            await self._session_service.remove_conference_session(conference_name)
        
        console_logger.info(f"Hung up {len(ccids)} calls in conference {conference_name}")
        return True


telnyx_handler = TelnyxHandler()