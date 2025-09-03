
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Blacklist(Base, TimestampMixin):
    __tablename__ = "blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)

    def __repr__(self):
        return f"<Blacklist(id={self.id}, phone_number='{self.phone_number}')>"