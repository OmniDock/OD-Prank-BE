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

        self.logger.info(f"Telnyx webhook event: {event_type} (call_control_id={call_control_id})")

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

        console_logger.info(f"Media WS connected: {call_control_id}")

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

            send_task = asyncio.create_task(
                self.stream_playlist_over_ws(ws, session, stream_id)
            )

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
            try:
                if send_task and not send_task.done():
                    send_task.cancel()
            except Exception:
                pass
            await ws.close()



    async def stream_playlist_over_ws(self, ws, session: CallSession, stream_id: Optional[str] = None):
        """
        Stream audio to Telnyx and broadcast BOTH directions to monitors.
        """
        try:
            if not session.voice_line_audios:
                return

            # Use only one audio file
            item = session.voice_line_audios[4]
            
            # Convert to 8kHz μ-law
            segment = AudioSegment.from_file(io.BytesIO(item.audio_data), format="mp3")
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

            # Stream with precise timing
            start_time = asyncio.get_event_loop().time()
            total_chunks_sent = 0
            
            while self._session_service.get_session(session.call_control_id):
                for chunk_b64 in chunks:                    
                    # Send to Telnyx
                    frame = {
                        "event": "media",
                        "media": {
                            "payload": chunk_b64
                        }
                    }

                    await ws.send_text(json.dumps(frame))                                        
                    total_chunks_sent += 1
                    next_time = start_time + (total_chunks_sent * 0.02)
                    sleep_time = next_time - asyncio.get_event_loop().time()
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                        
        except Exception as e:
            console_logger.error(f"Stream error: {e}")


telnyx_handler = TelnyxHandler()