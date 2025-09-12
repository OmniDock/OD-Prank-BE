from sqlalchemy import String, Text, Integer, Boolean, UUID, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin
import uuid


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"
    
    profile_uuid: Mapped[uuid.UUID] = mapped_column(PostgresUUID(as_uuid=True), default=uuid.uuid4,primary_key=True, unique=True, nullable=False)    
    user_id: Mapped[uuid.UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    user_email: Mapped[str] = mapped_column(String, nullable=False)

    #Subscription Info 
    prank_credits: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    call_credits: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    subscription_type: Mapped[str] = mapped_column(String, nullable=False, default="free")
    subscription_id: Mapped[str] = mapped_column(String, nullable=True)

    def __repr__(self):
        return f"<profile_uuid={self.profile_uuid}, user_id={self.user_id}, user_email={self.user_email}>"
