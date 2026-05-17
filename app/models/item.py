"""Inventory model — player's item holdings (seeds, harvests, fertilizers, tools)."""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Inventory(Base):
    """背包物品表 — 合并存储同类型物品。"""

    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="seed"
    )
    item_subtype: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "item_type", "item_subtype", name="uix_user_item"),
        CheckConstraint("quantity > 0", name="chk_quantity_positive"),
        CheckConstraint(
            "item_type IN ('seed', 'harvest', 'fertilizer', 'tool')",
            name="chk_item_type",
        ),
    )

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    @property
    def full_id(self) -> str:
        """返回 'item_type:item_subtype' 格式的唯一标识。"""
        return f"{self.item_type}:{self.item_subtype}"

    def add(self, amount: int = 1) -> None:
        """增加数量（调用方负责事务和锁）。"""
        if amount <= 0:
            raise ValueError("amount must be > 0")
        self.quantity += amount
        self.updated_at = datetime.now(timezone.utc)

    def remove(self, amount: int = 1) -> bool:
        """减少数量，返回是否成功。"""
        if amount <= 0:
            raise ValueError("amount must be > 0")
        if self.quantity < amount:
            return False
        self.quantity -= amount
        self.updated_at = datetime.now(timezone.utc)
        return True
