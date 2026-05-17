# Farm Repository

## 模块职责

`app/repositories/farm_repo.py` — 地块和作物的数据访问层（CRUD + 业务查询）。

## 设计决策

- 所有方法接受 `db: AsyncSession` 参数，不管理事务生命周期
- 返回模型实例而非字典，保持类型安全
- 批量查询使用 `selectinload` 预加载关联关系，避免 N+1

## Python 实现

```python
"""Farm repository — data access for plots and crops."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.farm import Plot, Crop


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
            select(Plot).options(selectinload(Plot.crop)).where(Plot.id == plot_id)
        )
        return result.scalar_one_or_none()

    async def get_user_plots(self, user_id: int) -> list[Plot]:
        """获取用户的所有地块（含作物，预加载）。"""
        result = await self.db.execute(
            select(Plot)
            .options(selectinload(Plot.crop))
            .where(Plot.user_id == user_id)
            .order_by(Plot.slot_index)
        )
        return list(result.scalars().all())

    async def create_plot(
        self,
        user_id: int,
        slot_index: int,
        is_locked: bool = False,
    ) -> Plot:
        """创建新地块。"""
        plot = Plot(user_id=user_id, slot_index=slot_index, is_locked=is_locked)
        self.db.add(plot)
        await self.db.flush()
        await self.db.refresh(plot)
        return plot

    async def unlock_plot(self, plot_id: int, user_id: int) -> bool:
        """解锁地块（只有所有者可以解锁）。返回是否成功。"""
        result = await self.db.execute(
            update(Plot)
            .where(Plot.id == plot_id, Plot.user_id == user_id, Plot.is_locked.is_(True))
            .values(is_locked=False)
        )
        await self.db.commit()
        return result.rowcount > 0

    # ------------------------------------------------------------------
    # Crop CRUD
    # ------------------------------------------------------------------

    async def get_crop(self, crop_id: int) -> Crop | None:
        """根据 ID 获取作物。"""
        result = await self.db.execute(select(Crop).where(Crop.id == crop_id))
        return result.scalar_one_or_none()

    async def get_mature_crops(self, user_id: int) -> list[Crop]:
        """获取用户已成熟的作物。"""
        now = datetime.now()
        result = await self.db.execute(
            select(Crop)
            .where(
                Crop.user_id == user_id,
                Crop.is_planted.is_(True),
                Crop.maturity_time <= now,
            )
            .order_by(Crop.plant_time)
        )
        return list(result.scalars().all())

    async def get_stealable_crops(
        self,
        user_id: int,
        exclude_user_ids: list[int] | None = None,
    ) -> list[Crop]:
        """获取可被偷的作物（已成熟 + 种植者不是白名单用户）。"""
        now = datetime.now()
        query = (
            select(Crop)
            .where(
                Crop.is_planted.is_(True),
                Crop.maturity_time <= now,
                Crop.harvested.is_(False),
            )
            .order_by(Crop.maturity_time.desc())
        )
        if exclude_user_ids:
            query = query.where(Crop.user_id.notin_(exclude_user_ids))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Plot-Crop Operations
    # ------------------------------------------------------------------

    async def plant_crop(
        self,
        plot_id: int,
        user_id: int,
        crop_type: str,
        growth_hours: float,
        seed_subtype: str | None = None,
    ) -> Crop:
        """在空地块上播种。"""
        from app.models.farm import Crop

        # 验证地块为空且属于该用户
        plot = await self.get_plot(plot_id)
        if not plot or plot.user_id != user_id:
            raise ValueError("Plot not found or not owned by user")
        if plot.crop is not None:
            raise ValueError("Plot already has a crop")

        from datetime import timedelta
        crop = Crop(
            plot_id=plot_id,
            user_id=user_id,
            crop_type=crop_type,
            seed_subtype=seed_subtype or crop_type,
            plant_time=datetime.now(),
            growth_hours=growth_hours,
            maturity_time=datetime.now() + timedelta(hours=growth_hours),
        )
        self.db.add(crop)

        # 更新地块状态
        plot.current_crop_id = crop.id
        plot.is_planted = True

        return crop

    async def harvest_crop(self, crop_id: int, user_id: int) -> Crop | None:
        """收获作物（标记为 harvested = True，作物记录保留不删除）。"""
        result = await self.db.execute(
            update(Crop)
            .where(Crop.id == crop_id, Crop.user_id == user_id)
            .values(harvested=True)
        )
        if result.rowcount == 0:
            return None
        await self.db.flush()

        # 清空地块
        crop = await self.get_crop(crop_id)
        if crop and crop.plot:
            crop.plot.current_crop_id = None
            crop.plot.is_planted = False
            await self.db.flush()

        return crop

    async def remove_crop(self, crop_id: int, user_id: int) -> bool:
        """永久移除作物（弃种或偷取后）。地块状态自动更新。"""
        result = await self.db.execute(
            update(Crop)
            .where(Crop.id == crop_id, Crop.user_id == user_id)
            .values(is_planted=False, harvested=True)
        )
        if result.rowcount == 0:
            return False

        # 清空地块引用
        crop = await self.get_crop(crop_id)
        if crop and crop.plot:
            crop.plot.current_crop_id = None
            crop.plot.is_planted = False

        return True

    async def count_unlocked_plots(self, user_id: int) -> int:
        """统计用户已解锁的地块数量。"""
        from sqlalchemy import func

        result = await self.db.execute(
            select(func.count(Plot.id)).where(
                Plot.user_id == user_id, Plot.is_locked.is_(False)
            )
        )
        return result.scalar_one()

    async def count_locked_plots(self, user_id: int) -> int:
        """统计用户未解锁的地块数量。"""
        from sqlalchemy import func

        result = await self.db.execute(
            select(func.count(Plot.id)).where(
                Plot.user_id == user_id, Plot.is_locked.is_(True)
            )
        )
        return result.scalar_one()
```

## 使用示例

```python
from app.repositories.farm_repo import FarmRepo

# 在路由中注入
async def get_my_farm(db: AsyncSession, user_id: int):
    repo = FarmRepo(db)
    plots = await repo.get_user_plots(user_id)
    return {"plots": plots, "unlockable": await repo.count_locked_plots(user_id)}

# 播种
repo = FarmRepo(db)
crop = await repo.plant_crop(plot_id=1, user_id=5, crop_type="wheat", growth_hours=24)

# 收获
repo = FarmRepo(db)
await repo.harvest_crop(crop_id=crop.id, user_id=5)
```
