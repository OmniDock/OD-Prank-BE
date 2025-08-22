from sqlalchemy import String, Text, Integer, ForeignKey, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin
from app.core.utils.enums import GenderEnum, ElevenLabsModelEnum, VoiceLineAudioStatusEnum


class VoiceLineAudio(Base, TimestampMixin):
    __tablename__ = "voice_line_audios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    voice_line_id: Mapped[int] = mapped_column(Integer, ForeignKey("voice_lines.id"), nullable=False, index=True)

    # TTS selection & settings
    voice_id: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[GenderEnum] = mapped_column(Enum(GenderEnum), nullable=True)
    model_id: Mapped[ElevenLabsModelEnum] = mapped_column(Enum(ElevenLabsModelEnum), nullable=False)
    voice_settings = mapped_column(JSON, nullable=True)

    # Storage & metrics
    storage_path: Mapped[str] = mapped_column(String(255), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=True)

    # Deterministic hashes for re-use
    text_hash: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    settings_hash: Mapped[str] = mapped_column(String(64), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=True, index=True)

    # Generation status
    status: Mapped[VoiceLineAudioStatusEnum] = mapped_column(Enum(VoiceLineAudioStatusEnum), nullable=False, default=VoiceLineAudioStatusEnum.PENDING)
    error: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationship back to voice line
    voice_line = relationship("VoiceLine", back_populates="audios")

    def __repr__(self):
        return f"<VoiceLineAudio(id={self.id}, voice_line_id={self.voice_line_id}, status='{self.status}')>"



