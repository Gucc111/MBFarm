# Farm Repository

## 模块职责

`app/repositories/farm_repo.py` — 地块、作物和背包物品的统一数据访问层（CRUD + 业务查询）。

## 设计决策

- 构造函数接收 `db: AsyncSession`，所有方法操作同一 db 实例
- 返回模型实例而非字典，保持类型安全
- 批量查询使用 `selectinload` 预加载关联关系，避免 N+1
- Inventory 操作合并在此文件中（FarmRepo 需要频繁操作种子库存）
- 不使用 `is_locked` 字段，地块解锁通过 `create_plot` 新建记录实现

## 方法列表

### Plot CRUD

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `get_plot(plot_id)` | `(plot_id: int)` | `Plot \| None` | 根据 ID 获取地块（含作物） |
| `get_plot_by_index(user_id, index)` | `(user_id, index)` | `Plot \| None` | 根据用户和编号获取地块 |
| `get_user_plots(user_id)` | `(user_id)` | `list[Plot]` | 用户所有地块（按 index 排序） |
| `create_plot(user_id, index)` | `(user_id, index)` | `Plot` | 创建新地块 |
| `create_initial_plots(user_id, count)` | `(user_id, count)` | `list[Plot]` | 新用户初始地块（1-based） |
| `count_unlocked_plots(user_id)` | `(user_id)` | `int` | 已解锁地块数量 |

### Crop CRUD

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `get_crop(crop_id)` | `(crop_id)` | `Crop \| None` | 根据 ID 获取作物 |
| `plant_crop(plot_id, user_id, seed_type, duration)` | `(plot_id, user_id, seed_type, duration)` | `Crop` | 在空地块上播种；验证地块归属+空置 |
| `harvest_crop(plot)` | `(plot: Plot)` | `Crop \| None` | 收获：标记 harvested + 清空地块 |
| `water_crop(plot)` | `(plot: Plot)` | `Crop` | 浇水：增加浇水次数 |

### Inventory CRUD（合并自原 item_repo）

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `get_item(user_id, item_type, item_subtype)` | `(user_id, item_type, item_subtype)` | `Inventory \| None` | 获取背包中指定物品 |
| `add_item(user_id, item_type, item_subtype, quantity)` | `(user_id, item_type, item_subtype, quantity)` | `Inventory` | 添加/叠加物品（upsert） |
| `remove_item(user_id, item_type, item_subtype, quantity)` | `(user_id, item_type, item_subtype, quantity)` | `bool` | 减少物品，归零则物理删除 |
| `get_user_inventory(user_id)` | `(user_id)` | `list[Inventory]` | 用户背包全部物品 |

## 完整 Python 实现

```python
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

    # ── Plot CRUD ──────────────────────────────────────────────────

    async def get_plot(self, plot_id: int) -> Plot | None:
        result = await self.db.execute(
            select(Plot)
            .options(selectinload(Plot.current_crop))
            .where(Plot.id == plot_id)
        )
        return result.scalar_one_or_none()

    async def get_plot_by_index(self, user_id: int, index: int) -> Plot | None:
        result = await self.db.execute(
            select(Plot)
            .options(selectinload(Plot.current_crop))
            .where(Plot.user_id == user_id, Plot.index == index)
        )
        return result.scalar_one_or_none()

    async def get_user_plots(self, user_id: int) -> list[Plot]:
        result = await self.db.execute(
            select(Plot)
            .options(selectinload(Plot.current_crop))
            .where(Plot.user_id == user_id)
            .order_by(Plot.index)
        )
        return list(result.scalars().all())

    async def create_plot(self, user_id: int, index: int) -> Plot:
        plot = Plot(user_id=user_id, index=index)
        self.db.add(plot)
        await self.db.flush()
        await self.db.refresh(plot)
        return plot

    async def create_initial_plots(self, user_id: int, count: int) -> list[Plot]:
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
        result = await self.db.execute(
            select(func.count(Plot.id)).where(Plot.user_id == user_id)
        )
        return result.scalar_one()

    # ── Crop CRUD ──────────────────────────────────────────────────

    async def get_crop(self, crop_id: int) -> Crop | None:
        result = await self.db.execute(select(Crop).where(Crop.id == crop_id))
        return result.scalar_one_or_none()

    async def plant_crop(self, plot_id: int, user_id: int, seed_type: str, duration: int) -> Crop:
        plot = await self.get_plot(plot_id)
        if not plot or plot.user_id != user_id:
            raise ValueError("Plot not found or not owned by user")
        if plot.crop_id is not None:
            raise ValueError("Plot already has a crop")

        now = datetime.now(timezone.utc)
        crop = Crop(
            plot_id=plot_id, seed_type=seed_type,
            plant_time=now, duration=duration, watered_times=0,
        )
        self.db.add(crop)
        await self.db.flush()
        await self.db.refresh(crop)

        plot.crop_id = crop.id
        plot.planted_at = now
        plot.last_watered_at = now
        return crop

    async def harvest_crop(self, plot: Plot) -> Crop | None:
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
        plot.watered_times += 1
        plot.last_watered_at = datetime.now(timezone.utc)
        if plot.current_crop:
            plot.current_crop.watered_times += 1
        await self.db.flush()
        return plot.current_crop  # type: ignore[return-value]

    # ── Inventory CRUD ─────────────────────────────────────────────

    async def get_item(self, user_id: int, item_type: str, item_subtype: str) -> Inventory | None:
        result = await self.db.execute(
            select(Inventory).where(
                Inventory.user_id == user_id,
                Inventory.item_type == item_type,
                Inventory.item_subtype == item_subtype,
            )
        )
        return result.scalar_one_or_none()

    async def add_item(self, user_id: int, item_type: str, item_subtype: str, quantity: int = 1) -> Inventory:
        existing = await self.get_item(user_id, item_type, item_subtype)
        if existing:
            existing.add(quantity)
        else:
            existing = Inventory(
                user_id=user_id, item_type=item_type,
                item_subtype=item_subtype, quantity=quantity,
            )
            self.db.add(existing)
        await self.db.flush()
        await self.db.refresh(existing)
        return existing

    async def remove_item(self, user_id: int, item_type: str, item_subtype: str, quantity: int = 1) -> bool:
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
        result = await self.db.execute(
            select(Inventory)
            .where(Inventory.user_id == user_id)
            .order_by(Inventory.item_type, Inventory.item_subtype)
        )
        return list(result.scalars().all())
```

## 使用示例

```python
from app.repositories.farm_repo import FarmRepo

repo = FarmRepo(db)

# 获取用户所有地块
plots = await repo.get_user_plots(user_id=5)

# 播种
crop = await repo.plant_crop(plot_id=1, user_id=5, seed_type="wheat", duration=1800)

# 收获
await repo.harvest_crop(plot)

# 浇水
await repo.water_crop(plot)

# 操作背包
await repo.add_item(user_id=5, item_type="seed", item_subtype="wheat", quantity=10)
ok = await repo.remove_item(user_id=5, item_type="seed", item_subtype="wheat", quantity=1)
```
