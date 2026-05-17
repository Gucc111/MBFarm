"""User ORM model."""

from datetime import datetime, timezone
from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(32), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    coins = Column(Integer, default=500, nullable=False)
    stamina = Column(Integer, default=100, nullable=False)
    xp = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=1, nullable=False)
    last_active_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("stamina >= 0", name="chk_stamina_non_negative"),
    )

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
