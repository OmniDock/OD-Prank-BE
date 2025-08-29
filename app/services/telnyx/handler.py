import io 
import base64 
import audioop 
import asyncio 
import json 
from typing import Optional 
from fastapi import WebSocket, WebSocketDisconnect
from pydub import AudioSegment 


from typing import Tuple

from app.core.database import AsyncSession 
from app.core.logging import console_logger 

from app.services.telnyx.client import TelnyxHTTPClient 
from app.services.telnyx.sessions import TelnyxSessionService, CallSession 
from app.services.audio_preload_service import AudioPreloadService 



class TelnyxHandler: 

    _session_service = TelnyxSessionService()
    _client = TelnyxHTTPClient()

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
        success, message, stats = await audio_service.preload_scenario_audio(user_id, scenario_id)
        if not success: 
            raise RuntimeError(f"Failed to preload audio for scenario {scenario_id}: {message}")
        
        # INITIATING THE CALL 
        call_leg_id, call_control_id, call_session_id, conference_name = await self._client.initiate_call(to_number)

        # STORE SESSION IN MEMORY (FOR NOW LATER WE WILL USE A DB OR CACHE)
        session = CallSession(
            user_id=user_id,
            scenario_id=scenario_id,
            to_number=to_number,
            from_number=self._client.FROM_NUMBER,
            call_leg_id=call_leg_id,
            call_control_id=call_control_id,
            call_session_id=call_session_id,
            conference_name=conference_name,
            voice_line_audios = audio_service.get_preloaded_audio(user_id, scenario_id)
        )
        self._session_service.add_session(session)

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

        self.logger.debug(f"Telnyx webhook event: {event_type} (call_control_id={call_control_id})")

        if not call_control_id:
            self.logger.warning("Webhook without call_control_id; ignoring.")
            return

        session = self._session_service.get_session(call_control_id)

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
                    self._session_service.add_ccid_to_conference(conference_name, call_control_id)
                    await self._client.start_media_stream(call_control_id)
                else:
                    self.logger.warning(f"No conference name found in custom headers")
                    return
            else:
                self.logger.warning(f"Unknown direction: {direction}")
                return 

        elif event_type == "call.answered":
            if session and session.conference_name:
                await self._client.start_media_stream(call_control_id)  

        elif event_type == "call.hangup":
            self._session_service.remove_session(call_control_id)



    async def handle_media_ws(self, ws: WebSocket, call_control_id: str):
        await ws.accept()

        console_logger.debug(f"Media WS connected: {call_control_id}")

        session = self._session_service.get_session(call_control_id)
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
        """
        Play a voice line over the media stream.
        """

        # CHECK IF SESSION EXISTS 
        session = self._session_service.get_session_by_conference(conference_name)
        if not session:
            raise RuntimeError(f"No session found for conference {conference_name}")
        
        # CHECK IF USER HAS ACCESS TO THE CONFERENCE 
        if session.user_id != user_id:
            raise RuntimeError(f"User {user_id} does not have access to conference {conference_name}")
        
        # GET THE VOICE LINE AUDIO 
        audio = session.voice_line_audios[voice_line_id]

        # CONVERT TO 8KHZ MU-LAW 
        segment = AudioSegment.from_file(io.BytesIO(audio.audio_data), format="mp3")
        segment = segment.set_frame_rate(8000).set_channels(1).set_sample_width(2).normalize()
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

        websockets = self._session_service.get_conference_websockets(conference_name)
        if not websockets:
            raise RuntimeError(f"No websockets found for conference {conference_name}")
        
        console_logger.info(f"Playing voice line {voice_line_id} for user {user_id} in conference {conference_name} to {len(websockets)} websockets")

        # Stream all chunks with proper timing (20ms per chunk)
        for chunk in chunks:
            for ws in websockets:
                await ws.send_text(json.dumps({"event": "media", "media": {"payload": chunk}}))
            await asyncio.sleep(0.02)


telnyx_handler = TelnyxHandler()