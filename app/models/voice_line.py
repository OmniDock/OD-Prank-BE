from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, Enum 
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin
from app.core.utils.enums import VoiceLineTypeEnum


class VoiceLine(Base, TimestampMixin):
    __tablename__ = "voice_lines"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), nullable=False)
    
    # Content
    text: Mapped[str] = mapped_column(Text, nullable=False) 
    type: Mapped[VoiceLineTypeEnum] = mapped_column(Enum(VoiceLineTypeEnum), nullable=False)  
    
    # Storage
    storage_url: Mapped[str] = mapped_column(String(255), nullable=True)

    # Relationship back to scenario
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="voice_lines")
    
    def __repr__(self):
        return f"<VoiceLine(id={self.id}, scenario_id={self.scenario_id}, type='{self.type}')>"