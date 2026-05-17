"""Farm repository — data access for plots, crops, and inventory."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.farm import Crop, Plot
from app.models.item import Inventory


class FarmRepo:
    """地块与作物的数据访问层。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Plot CRUD
    # ------------------------------------------------------------------

    async def get_plot(self, plot_id: int) -> Plot | None:
        """根据 ID 获取单个地块（含作物）。"""
        result = await self.db.execute(
            select(Plot).options(selectinload(Plot.current_crop)).where(Plot.id == plot_id)
        )
        return result.scalar_one_or_none()

    async def get_plot_by_index(self, user_id: int, index: int) -> Plot | None:
        """根据用户和索引获取地块（含作物）。"""
        result = await self.db.execute(
            select(Plot)
            .options(selectinload(Plot.current_crop))
            .where(Plot.user_id == user_id, Plot.index == index)
        )
        return result.scalar_one_or_none()

    async def get_user_plots(self, user_id: int) -> list[Plot]:
        """获取用户的所有地块（含作物，预加载）。"""
        result = await self.db.execute(
            select(Plot)
            .options(selectinload(Plot.current_crop))
            .where(Plot.user_id == user_id)
            .order_by(Plot.index)
        )
        return list(result.scalars().all())

    async def create_plot(self, user_id: int, index: int) -> Plot:
        """创建新地块。"""
        plot = Plot(user_id=user_id, index=index)
        self.db.add(plot)
        await self.db.flush()
        await self.db.refresh(plot)
        return plot

    async def create_initial_plots(self, user_id: int, count: int) -> list[Plot]:
        """为新用户创建初始地块（1-based index）。"""
        plots: list[Plot] = []
        for i in range(1, count + 1):
            plot = Plot(user_id=user_id, index=i)
            self.db.add(plot)
            plots.append(plot)
        await self.db.flush()
        for plot in plots:
            await self.db.refresh(plot)
        return plots

    async def count_unlocked_plots(self, user_id: int) -> int:
        """统计用户已解锁的地块数量。"""
        result = await self.db.execute(
            select(func.count(Plot.id)).where(Plot.user_id == user_id)
        )
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Crop CRUD
    # ------------------------------------------------------------------

    async def get_crop(self, crop_id: int) -> Crop | None:
        """根据 ID 获取作物。"""
        result = await self.db.execute(select(Crop).where(Crop.id == crop_id))
        return result.scalar_one_or_none()

    async def plant_crop(
        self,
        plot_id: int,
        user_id: int,
        seed_type: str,
        duration: int,
    ) -> Crop:
        """在空地块上播种。"""
        plot = await self.get_plot(plot_id)
        if not plot or plot.user_id != user_id:
            raise ValueError("Plot not found or not owned by user")
        if plot.crop_id is not None:
            raise ValueError("Plot already has a crop")

        now = datetime.now(timezone.utc)
        crop = Crop(
            plot_id=plot_id,
            seed_type=seed_type,
            plant_time=now,
            duration=duration,
            watered_times=0,
        )
        self.db.add(crop)
        await self.db.flush()
        await self.db.refresh(crop)

        # 更新地块状态
        plot.crop_id = crop.id
        plot.planted_at = now
        plot.last_watered_at = now

        return crop

    async def harvest_crop(self, plot: Plot) -> Crop | None:
        """收获作物：标记作物 harvested + 清空地块。"""
        crop = await self.get_crop(plot.crop_id)
        if crop is None:
            return None

        crop.is_harvested = True
        plot.crop_id = None
        plot.planted_at = None
        plot.last_watered_at = None
        plot.watered_times = 0
        await self.db.flush()

        return crop

    async def water_crop(self, plot: Plot) -> Crop:
        """对地块浇水：增加水次数，同时更新 Plot 和 Crop 的 watered_times。"""
        plot.watered_times += 1
        plot.last_watered_at = datetime.now(timezone.utc)

        if plot.current_crop:
            plot.current_crop.watered_times += 1

        await self.db.flush()

        return plot.current_crop  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Inventory CRUD
    # ------------------------------------------------------------------

    async def get_item(self, user_id: int, item_type: str, item_subtype: str) -> Inventory | None:
        """获取用户背包中的指定物品。"""
        stmt = (
            select(Inventory)
            .where(
                Inventory.user_id == user_id,
                Inventory.item_type == item_type,
                Inventory.item_subtype == item_subtype,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def add_item(self, user_id: int, item_type: str, item_subtype: str, quantity: int = 1) -> Inventory:
        """添加/增加物品数量。如果已存在则叠加，否则新建。"""
        existing = await self.get_item(user_id, item_type, item_subtype)
        if existing:
            existing.add(quantity)
        else:
            existing = Inventory(
                user_id=user_id,
                item_type=item_type,
                item_subtype=item_subtype,
                quantity=quantity,
            )
            self.db.add(existing)
        await self.db.flush()
        await self.db.refresh(existing)
        return existing

    async def remove_item(self, user_id: int, item_type: str, item_subtype: str, quantity: int = 1) -> bool:
        """减少物品数量，数量 <= 0 时物理删除。返回是否成功。"""
        item = await self.get_item(user_id, item_type, item_subtype)
        if item is None:
            return False
        if not item.remove(quantity):
            return False
        if item.quantity <= 0:
            await self.db.delete(item)
        await self.db.flush()
        return True

    async def get_user_inventory(self, user_id: int) -> list[Inventory]:
        """获取用户背包全部物品。"""
        result = await self.db.execute(
            select(Inventory).where(Inventory.user_id == user_id).order_by(Inventory.item_type, Inventory.item_subtype)
        )
        return list(result.scalars().all())
