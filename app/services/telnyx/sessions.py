from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
from app.services.audio_preload_service import PreloadedAudio
from app.services.cache_service import CacheService
from app.core.logging import console_logger
from app.core.utils.enums import VoiceLineTypeEnum
from fastapi import WebSocket


@dataclass
class CallSession:
    user_id: str
    scenario_id: int
    to_number: str
    from_number: str
    outbound_call_leg_id: Optional[str] = None
    outbound_call_control_id: Optional[str] = None
    outbound_call_session_id: Optional[str] = None
    webrtc_call_leg_id: Optional[str] = None
    webrtc_call_control_id: Optional[str] = None
    webrtc_call_session_id: Optional[str] = None
    conference_name: Optional[str] = None
    voice_line_audios: Optional[Dict[int, PreloadedAudio]] = None
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        data = asdict(self)
        data['user_id'] = str(self.user_id)
        # Convert PreloadedAudio objects to dicts
        if self.voice_line_audios:
            data['voice_line_audios'] = {
                str(k): {
                    **asdict(v),
                    'voice_line_type': v.voice_line_type.value
                } for k, v in self.voice_line_audios.items()
            }
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CallSession':
        """Create from dict (e.g., from Redis)"""
        # Convert voice_line_audios back to PreloadedAudio objects
        if data.get('voice_line_audios'):
            audios = {}
            for str_id, audio_dict in data['voice_line_audios'].items():
                audio_dict['voice_line_type'] = VoiceLineTypeEnum[audio_dict['voice_line_type']]
                # signed_url is optional, so it's fine if it's not present
                audios[int(str_id)] = PreloadedAudio(**audio_dict)
            data['voice_line_audios'] = audios
        return cls(**data)


class TelnyxSessionService:
    # WebSockets must stay in memory (can't serialize live connections)
    _websocket_sessions: Dict[str, Dict[int, WebSocket]] = {}
    
    # Configuration
    _session_ttl_seconds = 3600  

    async def add_conference_session(self, session: CallSession):

        console_logger.debug(f"Adding session {session.conference_name} to Redis")
        """Add a call session to Redis"""
        cache = await CacheService.get_global()
        
        # Store the session
        await cache.set_json(
            session.conference_name,
            session.to_dict(),
            ttl=self._session_ttl_seconds,
            prefix="telnyx:session"
        )
                
        console_logger.debug(f"Added session {session.conference_name} to Redis")

    async def get_conference_session(self, conference_name: str) -> Optional[CallSession]:
        """Get a call session from Redis"""
        cache = await CacheService.get_global()

        console_logger.debug(f"Getting session {conference_name} from Redis")
        
        # Try direct lookup first
        session_data = await cache.get_json(
            conference_name,
            prefix="telnyx:session"
        )
        
        if session_data:
            return CallSession.from_dict(session_data)
        
        console_logger.debug(f"No session found for conference {conference_name} in Redis")
        return None

    
    async def remove_conference_session(self, conference_name: str):
        """Remove a call session from Redis"""

        console_logger.debug(f"Removing session {conference_name} from Redis")
        cache = await CacheService.get_global()
        session = await self.get_conference_session(conference_name)
        await cache.delete(conference_name, prefix="telnyx:session")
        
        # Clean up WebSockets
        webrtc_ccid = session.webrtc_call_control_id
        outbound_ccid = session.outbound_call_control_id

        if webrtc_ccid:
            console_logger.debug(f"Removing WebSocket for webrtc_ccid {webrtc_ccid}")
            ws = self._websocket_sessions.get(webrtc_ccid)
            if ws:
                await ws.close()
                self._websocket_sessions.pop(webrtc_ccid, None)
        else:
            console_logger.debug(f"No WebSocket found for webrtc_ccid {webrtc_ccid}")

        if outbound_ccid:
            ws = self._websocket_sessions.get(outbound_ccid)
            if ws:
                await ws.close()
                self._websocket_sessions.pop(outbound_ccid, None)
        else:
            console_logger.debug(f"No WebSocket found for outbound_ccid {outbound_ccid}")

    async def get_websockets(self, conference_name: str) -> List[WebSocket]:
        session = await self.get_conference_session(conference_name)
        if not session:
            console_logger.debug(f"No session found for conference {conference_name}")
            return []
        
        ws_list = [] 

        webrtc_ccid = session.webrtc_call_control_id
        if webrtc_ccid:
            ws = self._websocket_sessions.get(webrtc_ccid)
            if ws:
                ws_list.append(ws)
            else:
                console_logger.debug(f"No WebSocket found for webrtc_ccid {webrtc_ccid}")
        else:
            console_logger.debug(f"No WebSocket found for webrtc_ccid {webrtc_ccid}")

        outbound_ccid = session.outbound_call_control_id
        if outbound_ccid:
            ws = self._websocket_sessions.get(outbound_ccid)
            if ws:
                ws_list.append(ws)
            else:
                console_logger.debug(f"No WebSocket found for outbound_ccid {outbound_ccid}")
        else:
            console_logger.debug(f"No WebSocket found for outbound_ccid {outbound_ccid}")

        return ws_list



    def add_websocket(self, call_control_id: str, ws: WebSocket) -> None:

        console_logger.debug(f"Adding WebSocket for call_control_id {call_control_id}")
        bucket = self._websocket_sessions.setdefault(call_control_id, {})
        bucket[id(ws)] = ws



    def remove_websocket(self, call_control_id: str, ws: WebSocket) -> None:

        console_logger.debug(f"Removing WebSocket for call_control_id {call_control_id}")
        bucket = self._websocket_sessions.get(call_control_id)
        if not bucket:
            console_logger.debug(f"No WebSocket found for call_control_id {call_control_id}")
            return
        bucket.pop(id(ws), None)
        if not bucket:
            self._websocket_sessions.pop(call_control_id, None)
        else:
            console_logger.debug(f"No WebSocket found for call_control_id {call_control_id}")


    async def add_ccid_to_conference(self, conference_name: str, ccid: str) -> None:
        cache = await CacheService.get_global()
        await cache.set(f"{ccid}", conference_name, ttl=self._session_ttl_seconds, prefix="telnyx:conf_ccids")

    async def get_conference_name_by_ccid(self, ccid: str) -> Optional[str]:
        cache = await CacheService.get_global()
        conference_name = await cache.get(f"{ccid}", prefix="telnyx:conf_ccids")
        console_logger.debug(f"Conference name by ccid {ccid}: {conference_name}")
        return conference_name


    async def get_ccids_by_conference(self, conference_name: str) -> List[str]:
        session = await self.get_conference_session(conference_name)
        if not session:
            console_logger.debug(f"No session found for conference {conference_name}")
            return []
        
        console_logger.debug(f"CCIDs by conference {conference_name}: {session.webrtc_call_control_id, session.outbound_call_control_id}")
        return [session.webrtc_call_control_id, session.outbound_call_control_id]