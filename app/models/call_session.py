from sqlalchemy import String, Text, Integer, ForeignKey, Enum, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin
from app.core.utils.enums import CallStatusEnum
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class CallSession(Base, TimestampMixin):
    __tablename__ = "call_sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False, index=True)
    scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), nullable=False)
    
    # Telnyx call information
    telnyx_call_id: Mapped[str] = mapped_column(String(100), nullable=True, unique=True, index=True)
    
    # Conference information for listen-only audio streaming
    conference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    webrtc_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    conference_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Call details
    to_number: Mapped[str] = mapped_column(String(20), nullable=False)
    from_number: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[CallStatusEnum] = mapped_column(Enum(CallStatusEnum), nullable=False, default=CallStatusEnum.INITIATED)
    
    # Call timing
    initiated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Call metadata
    machine_detection_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    hangup_cause: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Additional data from Telnyx
    telnyx_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    scenario = relationship("Scenario", back_populates="call_sessions")
    events: Mapped[List["CallEvent"]] = relationship(
        "CallEvent", 
        back_populates="call_session",
        cascade="all, delete-orphan",
        order_by="CallEvent.created_at"
    )
    
    def __repr__(self):
        return f"<CallSession(id={self.id}, telnyx_call_id='{self.telnyx_call_id}', status='{self.status}')>"
