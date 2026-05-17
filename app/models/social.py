"""Social models — friend relationships and blocks."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class FriendshipStatus(str, Enum):
    """好友关系状态枚举。"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class Friendship(Base):
    """好友关系表 — 有向关系，双向好友需两条记录。"""

    __tablename__ = "friendships"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    friend_id = Column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(
        String(16),
        nullable=False,
        server_default=FriendshipStatus.PENDING,
    )
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships (lazy-loaded, used by selectinload in the repo)
    user = relationship("User", foreign_keys=[user_id], lazy="selectin")
    friend = relationship("User", foreign_keys=[friend_id], lazy="selectin")

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "friend_id", name="uix_user_friend"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'blocked')",
            name="chk_friendship_status",
        ),
    )

    def accept(self) -> None:
        self.status = FriendshipStatus.ACCEPTED
        self.updated_at = datetime.now(timezone.utc)

    def reject(self) -> None:
        self.status = FriendshipStatus.REJECTED
        self.updated_at = datetime.now(timezone.utc)

    def block(self) -> None:
        self.status = FriendshipStatus.BLOCKED
        self.updated_at = datetime.now(timezone.utc)

    @property
    def is_active(self) -> bool:
        return self.status in (FriendshipStatus.PENDING, FriendshipStatus.ACCEPTED)
