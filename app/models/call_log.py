from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base
import datetime

class CallLog(Base):
    __tablename__ = "call_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    to_number = Column(String, nullable=False, index=True)
    scenario_id = Column(Integer, ForeignKey("scenario.id"), nullable=False)
    call_timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    call_status = Column(String, nullable=True)
    duration = Column(Integer, nullable=True)
    metadata = Column(JSON, nullable=True)

    scenario = relationship("Scenario", back_populates="call_logs")

