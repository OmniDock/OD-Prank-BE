from sqlalchemy import String, Text, Integer, ForeignKey, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin
from app.core.utils.enums import CallEventTypeEnum
from typing import Optional, Dict, Any


class CallEvent(Base, TimestampMixin):
    __tablename__ = "call_events"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_session_id: Mapped[int] = mapped_column(Integer, ForeignKey("call_sessions.id"), nullable=False, index=True)
    
    # Event details
    event_type: Mapped[CallEventTypeEnum] = mapped_column(Enum(CallEventTypeEnum), nullable=False)
    telnyx_event_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    
    # Voice line context (if event is related to voice line playback)
    voice_line_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("voice_lines.id"), nullable=True)
    voice_line_audio_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("voice_line_audios.id"), nullable=True)
    
    # Event data from Telnyx webhook
    event_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Additional context
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    call_session = relationship("CallSession", back_populates="events")
    voice_line = relationship("VoiceLine")
    voice_line_audio = relationship("VoiceLineAudio")
    
    def __repr__(self):
        return f"<CallEvent(id={self.id}, type='{self.event_type}', call_session_id={self.call_session_id})>"
