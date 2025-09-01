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



class TelnyxHandler: 

    _session_service = TelnyxSessionService()
    _client = TelnyxHTTPClient()
    # Active playback tasks stay in memory (process-specific, can't serialize asyncio.Task)
    # These are ephemeral and will be recreated if the process restarts
    _active_playbacks_tasks: Dict[str, asyncio.Task] = {}

    def __init__(self):
        self.logger = console_logger 


    async def initiate_call(
            self,
            db_session: AsyncSession,
            user_id: str,
            scenario_id: int,
            to_number: str,
    ) -> Tuple[str, str, str, str]:
        """
        Initiate a call to the given number.
        """
        
        # PRELOADING AUDIO (TO BE EXCHANGED LATER)
        audio_service = AudioPreloadService(db_session)
        success, message = await audio_service.preload_scenario_audio(user_id, scenario_id)
        if not success: 
            raise RuntimeError(f"Failed to preload audio for scenario {scenario_id}: {message}")
        
        # INITIATING THE CALL 
        call_leg_id, call_control_id, call_session_id, conference_name = await self._client.initiate_call(to_number)


        preloaded_audio = await audio_service.get_preloaded_audio(user_id, scenario_id)
        console_logger.debug(f"Preloaded audio: {preloaded_audio}")

        # STORE SESSION IN MEMORY (FOR NOW LATER WE WILL USE A DB OR CACHE)
        session = CallSession(
            user_id=str(user_id),
            scenario_id=scenario_id,
            to_number=to_number,
            from_number=self._client.FROM_NUMBER,
            call_leg_id=call_leg_id,
            call_control_id=call_control_id,
            call_session_id=call_session_id,
            conference_name=conference_name,
            voice_line_audios = preloaded_audio
        )
        await self._session_service.add_session(session)

        self.logger.info(f"Initiated call {call_leg_id} (control_id={call_control_id}) to {to_number}")

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

        self.logger.info(f"Telnyx webhook event: {event_type} (call_control_id={call_control_id})")

        if not call_control_id:
            self.logger.warning("Webhook without call_control_id; ignoring.")
            return

        session = await self._session_service.get_session(call_control_id)

        if event_type == "call.initiated":
            # Differentiate between inbound and outbound calls. 
            direction = payload.get("direction")
            if direction == "outgoing":
                # Outbound Calls from the API are answered by the called person.
                pass 
            elif direction == "incoming":
                # Inbound Calls from Browsers need to be answered and joined to the conference. 
                custom_headers = { (h.get("name") or "").lower(): (h.get("value") or "") for h in (payload.get("custom_headers") or []) }
                conference_name = custom_headers.get("x-conference-name")
                if conference_name:
                    await self._client.answer_with_retry(call_control_id)
                    await self._client.join_conference_by_name(call_control_id, conference_name, mute=True)
                    await self._session_service.add_ccid_to_conference(conference_name, call_control_id)
                    await self._client.start_media_stream(call_control_id)
                else:
                    self.logger.warning(f"No conference name found in custom headers")
                    return
            else:
                self.logger.warning(f"Unknown direction: {direction}")
                return 

        elif event_type == "call.answered":
            if session and session.conference_name:
                pass
                await self._client.start_media_stream(call_control_id)  

        elif event_type == "call.hangup":
            await self._session_service.remove_session(call_control_id)



    async def handle_media_ws(self, ws: WebSocket, call_control_id: str):
        await ws.accept()

        console_logger.info(f"Media WS connected: {call_control_id}")

        session = await self._session_service.get_session(call_control_id)
        if not session:
            await ws.close()
            return
        
        self._session_service.add_websocket(call_control_id, ws)

        send_task = None
        try:
            stream_id = None
            while True:
                msg = await ws.receive_text()
                data = json.loads(msg)
                if data.get("event") == "start":
                    stream_id = data.get("stream_id") or data.get("streamId")
                    break
            # Keep consuming inbound to keep socket healthy
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
            self._session_service.remove_websocket(call_control_id, ws)
            await ws.close()


    async def play_voice_line(self, user_id: str, conference_name: str, voice_line_id: int):
        # Validate session and ownership
        session = await self._session_service.get_session_by_conference(conference_name)
        if not session:
            raise RuntimeError(f"No session found for conference {conference_name}")
        if str(session.user_id) != user_id:
            raise RuntimeError(f"User {user_id} does not have access to conference {conference_name}")

        # Ensure voice line exists in session
        if not session.voice_line_audios or voice_line_id not in session.voice_line_audios:
            raise RuntimeError(f"Voice line {voice_line_id} not found in session")

        audio = session.voice_line_audios[voice_line_id]

        # Generate a short-lived signed URL from Supabase Storage
        tts = TTSService()
        signed_url = await tts.get_audio_url(audio.storage_path, expires_in=600)
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
        session = await self._session_service.get_session_by_conference(conference_name)
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
        session = await self._session_service.get_session_by_conference(conference_name)
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
            await self._session_service.remove_session(ccid)
        
        console_logger.info(f"Hung up {len(ccids)} calls in conference {conference_name}")
        return True


telnyx_handler = TelnyxHandler()