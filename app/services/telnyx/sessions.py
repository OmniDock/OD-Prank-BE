from dataclasses import dataclass 
from typing import Optional, Dict, List, Set
from app.services.audio_preload_service import PreloadedAudio
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
    conference_name: Optional[str] = None
    voice_line_audios: Optional[Dict[int, PreloadedAudio]] = None


class TelnyxSessionService:
    _sessions: Dict[str, CallSession] = {}
    _websocket_sessions: Dict[str, Dict[int, WebSocket]] = {}
    _conf_to_ccids: Dict[str, Set[str]] = {}  

    def add_session(self, session: CallSession):
        self._sessions[session.call_control_id] = session
        if session.conference_name:
            bucket = self._conf_to_ccids.setdefault(session.conference_name, set())
            bucket.add(session.call_control_id)

    def get_session(self, call_control_id: str) -> Optional[CallSession]:
        session = self._sessions.get(call_control_id)
        if session: 
            return session 
        else: 
            for conf in self._conf_to_ccids.keys():
                if call_control_id in self._conf_to_ccids[conf]:
                    ccids = self._conf_to_ccids[conf]
                    for ccid in ccids:
                        session = self._sessions.get(ccid)
                        if session:
                            return session
        return None
    
    def remove_session(self, call_control_id: str):
        sess = self._sessions.pop(call_control_id, None) 
        self._websocket_sessions.pop(call_control_id, None)
        if sess and sess.conference_name:
            bucket = self._conf_to_ccids.get(sess.conference_name)
            if bucket:
                bucket.discard(call_control_id)
                if not bucket:
                    self._conf_to_ccids.pop(sess.conference_name, None)

    def add_websocket(self, call_control_id: str, ws: WebSocket) -> None:
        bucket = self._websocket_sessions.setdefault(call_control_id, {})
        bucket[id(ws)] = ws

    def remove_websocket(self, call_control_id: str, ws: WebSocket) -> None:
        bucket = self._websocket_sessions.get(call_control_id)
        if not bucket:
            return
        bucket.pop(id(ws), None)
        if not bucket:
            self._websocket_sessions.pop(call_control_id, None)

    def get_websockets(self, call_control_id: str) -> List[WebSocket]:
        return list(self._websocket_sessions.get(call_control_id, {}).values())

    def get_ccids_by_conference(self, conference_name: str) -> List[str]:
        return list(self._conf_to_ccids.get(conference_name, set()))
    
    def add_ccid_to_conference(self, conference_name: str, ccid: str):
        bucket = self._conf_to_ccids.setdefault(conference_name, set())
        bucket.add(ccid)

    def get_conference_websockets(self, conference_name: str) -> List[WebSocket]:
        out: List[WebSocket] = []
        for ccid in self.get_ccids_by_conference(conference_name):
            out.extend(self.get_websockets(ccid))
        return out
    
