from sqlalchemy import String, Text, Integer, Boolean, UUID, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin
import uuid


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"
    
    profile_uuid: Mapped[uuid.UUID] = mapped_column(PostgresUUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)    
    user_id: Mapped[uuid.UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("auth.users.id"), nullable=False)

    #Subscription Info 
    prank_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    call_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    subscription_type: Mapped[str] = mapped_column(String, nullable=True)
    subscription_id: Mapped[str] = mapped_column(String, nullable=True)

    def __repr__(self):
        return f"<UserProfile(id={self.id}, profile_uuid={self.profile_uuid}, user_id={self.user_id})>"