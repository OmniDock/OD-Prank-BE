from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Set
from app.services.audio_preload_service import PreloadedAudio
from app.services.cache_service import CacheService
from app.core.logging import console_logger
from app.core.utils.enums import VoiceLineTypeEnum
from fastapi import WebSocket
import json

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
                audios[int(str_id)] = PreloadedAudio(**audio_dict)
            data['voice_line_audios'] = audios
        return cls(**data)


class TelnyxSessionService:
    # WebSockets must stay in memory (can't serialize live connections)
    _websocket_sessions: Dict[str, Dict[int, WebSocket]] = {}
    
    # Configuration
    _session_ttl_seconds = 3600  # 1 hour TTL for call sessions  

    async def add_session(self, session: CallSession):
        """Add a call session to Redis"""
        cache = await CacheService.get_global()
        
        # Store the session
        await cache.set_json(
            session.call_control_id,
            session.to_dict(),
            ttl=self._session_ttl_seconds,
            prefix="telnyx:session"
        )
        
        # Update conference mapping if needed
        if session.conference_name:
            # Get existing ccids for this conference
            ccids = await cache.get_json(
                session.conference_name,
                prefix="telnyx:conf_ccids"
            ) or []
            
            # Add this ccid if not already present
            if session.call_control_id not in ccids:
                ccids.append(session.call_control_id)
                await cache.set_json(
                    session.conference_name,
                    ccids,
                    ttl=self._session_ttl_seconds,
                    prefix="telnyx:conf_ccids"
                )
        
        console_logger.info(f"Added session {session.call_control_id} to Redis")

    async def get_session(self, call_control_id: str) -> Optional[CallSession]:
        """Get a call session from Redis"""
        cache = await CacheService.get_global()
        
        # Try direct lookup first
        session_data = await cache.get_json(
            call_control_id,
            prefix="telnyx:session"
        )
        
        if session_data:
            return CallSession.from_dict(session_data)
        
        # If not found directly, check if it's part of a conference
        # (This handles the case where we have a conference member ccid)
        # Note: This is a more expensive operation, consider if really needed
        return None
    
    async def get_session_by_conference(self, conference_name: str) -> Optional[CallSession]:
        """Get the first session associated with a conference"""
        cache = await CacheService.get_global()
        
        # Get ccids for this conference
        ccids = await cache.get_json(
            conference_name,
            prefix="telnyx:conf_ccids"
        ) or []
        
        # Return the first valid session
        for ccid in ccids:
            session_data = await cache.get_json(
                ccid,
                prefix="telnyx:session"
            )
            if session_data:
                return CallSession.from_dict(session_data)
        
        return None
    
    async def remove_session(self, call_control_id: str):
        """Remove a call session from Redis"""
        cache = await CacheService.get_global()
        
        # Get session to check conference name
        session_data = await cache.get_json(
            call_control_id,
            prefix="telnyx:session"
        )
        
        # Remove the session
        await cache.delete(call_control_id, prefix="telnyx:session")
        
        # Clean up WebSockets
        self._websocket_sessions.pop(call_control_id, None)
        
        # Update conference mapping if needed
        if session_data and session_data.get('conference_name'):
            conference_name = session_data['conference_name']
            ccids = await cache.get_json(
                conference_name,
                prefix="telnyx:conf_ccids"
            ) or []
            
            if call_control_id in ccids:
                ccids.remove(call_control_id)
                if ccids:
                    # Update the list
                    await cache.set_json(
                        conference_name,
                        ccids,
                        ttl=self._session_ttl_seconds,
                        prefix="telnyx:conf_ccids"
                    )
                else:
                    # Remove empty conference mapping
                    await cache.delete(conference_name, prefix="telnyx:conf_ccids")
        
        console_logger.info(f"Removed session {call_control_id} from Redis")

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


    async def get_ccids_by_conference(self, conference_name: str) -> List[str]:
        """Get all call control IDs for a conference"""
        cache = await CacheService.get_global()
        ccids = await cache.get_json(
            conference_name,
            prefix="telnyx:conf_ccids"
        ) or []
        return ccids
    
    async def add_ccid_to_conference(self, conference_name: str, ccid: str):
        """Add a call control ID to a conference mapping"""
        cache = await CacheService.get_global()
        
        # Get existing ccids
        ccids = await cache.get_json(
            conference_name,
            prefix="telnyx:conf_ccids"
        ) or []
        
        # Add if not present
        if ccid not in ccids:
            ccids.append(ccid)
            await cache.set_json(
                conference_name,
                ccids,
                ttl=self._session_ttl_seconds,
                prefix="telnyx:conf_ccids"
            )

    async def get_conference_websockets(self, conference_name: str) -> List[WebSocket]:
        """Get all WebSockets for a conference"""
        out: List[WebSocket] = []
        ccids = await self.get_ccids_by_conference(conference_name)
        for ccid in ccids:
            out.extend(self.get_websockets(ccid))
        return out
    
