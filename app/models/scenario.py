from sqlalchemy import String, Text, Integer, Boolean, UUID, Enum
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin
from typing import List
import enum


class LanguageEnum(enum.Enum):
    ENGLISH = "en"
    GERMAN = "de"


class Scenario(Base, TimestampMixin):
    __tablename__ = "scenarios"
    __versioned__ = {}
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    language: Mapped[LanguageEnum] = mapped_column(Enum(LanguageEnum), nullable=False)

    is_safe: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_not_safe_reason: Mapped[str] = mapped_column(Text, nullable=True)
    
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    voice_lines: Mapped[List["VoiceLine"]] = relationship(
        "VoiceLine", 
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="VoiceLine.order_index"
    )
    
    def __repr__(self):
        return f"<Scenario(id={self.id}, title='{self.title}', language='{self.language.value}')>"

