"""Steal log model — records of crop stealing between friends."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Integer, String

from app.core.database import Base


class StealLog(Base):
    """偷菜记录表。"""

    __tablename__ = "steal_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stealer_id = Column(BigInteger, nullable=False, index=True)
    victim_id = Column(BigInteger, nullable=False, index=True)
    stolen_crop_type = Column(String(32), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    stolen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
