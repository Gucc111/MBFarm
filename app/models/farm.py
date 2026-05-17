"""Farm data models: Plot and Crop.

Plot — A physical farming plot owned by a user.
Crop — A single planting lifecycle on a plot.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ---------------------------------------------------------------------------
# Plot (地块)
# ---------------------------------------------------------------------------

class Plot(Base):
    """玩家的一块耕地。"""

    __tablename__ = "plots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    crop_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("crops.id", ondelete="SET NULL"), nullable=True
    )
    watered_times: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    planted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_watered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    current_crop = relationship(
        "Crop",
        back_populates="plot",
        lazy="selectin",
        foreign_keys="Crop.plot_id",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "index", name="uix_user_plot_index"),
        CheckConstraint("level BETWEEN 1 AND 5", name="chk_plot_level"),
        CheckConstraint("watered_times >= 0", name="chk_watered_non_negative"),
    )

    def has_crop(self) -> bool:
        """地块是否有当前作物。"""
        return self.crop_id is not None


# ---------------------------------------------------------------------------
# Crop (作物)
# ---------------------------------------------------------------------------

class Crop(Base):
    """单次种植的生命周期记录。"""

    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seed_type: Mapped[str] = mapped_column(String(32), nullable=False)
    plant_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    watered_times: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_harvested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    plot = relationship(
        "Plot",
        back_populates="current_crop",
        lazy="select",
        foreign_keys="Crop.plot_id",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("watered_times >= 0", name="chk_crop_watered_non_negative"),
    )
