from sqlalchemy import String, Text, Integer, Boolean, UUID, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin
import uuid


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"
    
    profile_uuid: Mapped[uuid.UUID] = mapped_column(PostgresUUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)    
    user_id: Mapped[uuid.UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("auth.users.id"), nullable=False)

    def __repr__(self):
        return f"<UserProfile(id={self.id}, profile_uuid={self.profile_uuid}, user_id={self.user_id})>"