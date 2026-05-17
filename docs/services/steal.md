# 偷菜服务 (StealService)

> 偷菜业务逻辑：检查目标农田、执行偷取、冷却与每日上限。  
> 对应代码文件：`app/services/steal.py`

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **偷菜** | 校验好友 → 检查冷却/上限/体力 → 查找目标成熟作物 → 偷取 → 记录日志 |
| **冷却检查** | 对同一目标用户 30 分钟内只能偷一次 |
| **每日上限** | 每天最多偷 `SYSTEM.max_daily_steal` (3) 次 |
| **体力消耗** | 每次偷菜消耗 `STAMINA.steal_cost` (3) 点体力 |

---

## 2. 设计决策

### 异常处理

统一使用 `app/core/exceptions.py` 中定义的 `AppError` 子类，由 `main.py` 的全局异常处理器转换为 JSON 响应：

| 业务场景 | 异常类 | HTTP 状态码 |
|----------|--------|-------------|
| 偷自己的菜 | `ForbiddenError("不能偷自己的作物")` | 403 |
| 不是好友 | `ForbiddenError("只能偷好友的作物")` | 403 |
| 冷却中 | `AppValidationError("偷菜冷却中，请 30 分钟后再试")` | 422 |
| 达到每日上限 | `ConflictError("今日偷菜次数已达上限 (N)")` | 409 |
| 无成熟作物 | `NotFoundError("目标没有成熟作物可偷")` | 404 |
| 体力不足 | `AppValidationError("体力不足...")` | 422 |

### 偷取逻辑

偷取目标地块上的成熟作物。偷取后：
- 目标地块上的作物被移除（`FarmRepo.harvest_crop(plot)` 标记 `is_harvested=True` 并清空地块）
- 偷菜者的 inventory 中增加偷取的作物（`FarmRepo.add_item(user_id, "harvest", seed_type, quantity=1)`）
- 随机从所有成熟地块中选择一个

### 冷却与上限

- **冷却**：对同一目标用户，30 分钟内只能偷一次。通过 `StealLog` 模型记录，在 service 内部 `_check_cooldown()` 查询。
- **每日上限**：每天最多偷 `SYSTEM.max_daily_steal` 次，以自然日（00:00 UTC）为界。在 service 内部 `_count_today_steals()` 查询。

### 体力恢复

偷菜前通过 `game_engine.restore_stamina()` 计算离线恢复的体力。

### 依赖说明

- 偷菜日志（`StealLog`）直接由 `StealService` 写入 `db`，不经过独立的 repository
- 冷却和每日计数查询也在 service 内部完成（`_check_cooldown` / `_count_today_steals`）
- 使用 `FarmRepo` 的 `add_item` 方法添加偷取到的作物（ItemRepo 不存在，物品操作在 FarmRepo 中）
- 使用 `SocialRepo.is_friend()` 检查双向好友关系
- 使用 `SEED_MAP`（dict）而非 `SEEDS`（tuple）查找种子配置

### StealLog 模型

```python
class StealLog(Base):
    __tablename__ = "steal_logs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stealer_id = Column(BigInteger, nullable=False, index=True)
    victim_id = Column(BigInteger, nullable=False, index=True)
    stolen_crop_type = Column(String(32), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    stolen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
```

---

## 3. 方法列表

| 方法 | 参数 | 返回值 | 异常 |
|------|------|--------|------|
| `steal(user_id, target_user_id)` | — | `dict` (seed_type, seed_name, quantity, value) | 403/422/409/404 |
| `get_my_stolen(user_id)` | — | `dict` (records, total) | — |
| `get_being_stolen(user_id)` | — | `dict` (records, total) | — |
| `_check_cooldown(stealer_id, victim_id)` | — | `bool` | — |
| `_count_today_steals(user_id)` | — | `int` | — |

---

## 4. 完整 Python 实现

```python
"""Steal service — business logic for stealing crops from friends."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SEED_MAP, STAMINA, SYSTEM
from app.core.exceptions import (
    AppValidationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.models.steal import StealLog
from app.repositories.farm_repo import FarmRepo
from app.repositories.social_repo import SocialRepo
from app.repositories.user_repo import UserRepository
from app.services.game_engine import is_mature, restore_stamina


COOLDOWN_SECONDS = 30 * 60  # 30 minutes


class StealService:
    """偷菜业务逻辑。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.farm_repo = FarmRepo(db)
        self.user_repo = UserRepository(db)
        self.social_repo = SocialRepo(db)

    async def steal(self, user_id: int, target_user_id: int) -> dict:
        """偷取目标用户的地块上的成熟作物。"""
        if user_id == target_user_id:
            raise ForbiddenError("不能偷自己的作物")

        # 检查好友关系
        is_f = await self.social_repo.is_friend(user_id, target_user_id)
        if not is_f:
            raise ForbiddenError("只能偷好友的作物")

        # 检查冷却
        cooldown_ok = await self._check_cooldown(user_id, target_user_id)
        if not cooldown_ok:
            raise AppValidationError("偷菜冷却中，请 30 分钟后再试")

        # 检查每日上限
        today_count = await self._count_today_steals(user_id)
        if today_count >= SYSTEM.max_daily_steal:
            raise ConflictError(f"今日偷菜次数已达上限 ({SYSTEM.max_daily_steal})")

        # 查找目标用户成熟地块
        plots = await self.farm_repo.get_user_plots(target_user_id)
        mature_plots = []
        for plot in plots:
            if plot.crop_id is None:
                continue
            crop = await self.farm_repo.get_crop(plot.crop_id)
            if crop is None or crop.is_harvested:
                continue
            seed_config = SEED_MAP.get(crop.seed_type)
            if seed_config and is_mature(
                crop.plant_time, crop.duration, crop.watered_times, seed_config.water_bonus
            ):
                mature_plots.append((plot, crop, seed_config))

        if not mature_plots:
            raise NotFoundError("目标没有成熟作物可偷")

        # 随机选一个成熟地块
        plot, crop, seed_config = random.choice(mature_plots)

        # 消耗体力
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("用户不存在")

        if user.last_active_at is not None:
            user.stamina = restore_stamina(
                current_stamina=user.stamina,
                last_active=user.last_active_at,
                max_stamina=STAMINA.max_value,
                restore_per_minute=STAMINA.regen_per_min,
            )
        if user.stamina < STAMINA.steal_cost:
            raise AppValidationError(
                f"体力不足（需要 {STAMINA.steal_cost}，当前 {user.stamina}）"
            )
        user.stamina -= STAMINA.steal_cost
        user.last_active_at = datetime.now(timezone.utc)

        # 偷取作物：从目标地块移除，加到偷菜者背包
        await self.farm_repo.harvest_crop(plot)
        await self.farm_repo.add_item(user_id, "harvest", crop.seed_type, quantity=1)

        # 记录偷菜日志
        steal_log = StealLog(
            stealer_id=user_id,
            victim_id=target_user_id,
            stolen_crop_type=crop.seed_type,
            quantity=1,
        )
        self.db.add(steal_log)
        await self.db.flush()

        return {
            "seed_type": crop.seed_type,
            "seed_name": seed_config.name,
            "quantity": 1,
            "value": seed_config.sell_price,
        }

    async def _check_cooldown(self, stealer_id: int, victim_id: int) -> bool:
        """检查对同一目标的冷却是否已过。"""
        now = datetime.now(timezone.utc)
        cooldown_cutoff = now - timedelta(seconds=COOLDOWN_SECONDS)

        result = await self.db.execute(
            select(StealLog).where(
                and_(
                    StealLog.stealer_id == stealer_id,
                    StealLog.victim_id == victim_id,
                    StealLog.stolen_at >= cooldown_cutoff,
                )
            )
        )
        recent = result.scalar_one_or_none()
        return recent is None

    async def _count_today_steals(self, user_id: int) -> int:
        """统计今日偷菜次数。"""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        result = await self.db.execute(
            select(func.count(StealLog.id)).where(
                and_(
                    StealLog.stealer_id == user_id,
                    StealLog.stolen_at >= today_start,
                )
            )
        )
        return result.scalar_one()

    async def get_my_stolen(self, user_id: int) -> dict:
        """查看偷到的作物。"""
        result = await self.db.execute(
            select(StealLog)
            .where(StealLog.stealer_id == user_id)
            .order_by(StealLog.stolen_at.desc())
        )
        records = list(result.scalars().all())
        return {
            "records": [
                {
                    "id": r.id,
                    "victim_id": r.victim_id,
                    "stolen_crop_type": r.stolen_crop_type,
                    "quantity": r.quantity,
                    "stolen_at": r.stolen_at.isoformat(),
                }
                for r in records
            ],
            "total": len(records),
        }

    async def get_being_stolen(self, user_id: int) -> dict:
        """查看被别人偷走的作物。"""
        result = await self.db.execute(
            select(StealLog)
            .where(StealLog.victim_id == user_id)
            .order_by(StealLog.stolen_at.desc())
        )
        records = list(result.scalars().all())
        return {
            "records": [
                {
                    "id": r.id,
                    "stealer_id": r.stealer_id,
                    "stolen_crop_type": r.stolen_crop_type,
                    "quantity": r.quantity,
                    "stolen_at": r.stolen_at.isoformat(),
                }
                for r in records
            ],
            "total": len(records),
        }
```

---

## 5. 依赖关系

```
StealService
├── FarmRepo (查询目标地块/作物、收获、添加物品)
├── UserRepository (体力管理)
├── SocialRepo.is_friend() (好友校验)
├── models.steal.StealLog (偷菜日志)
├── core.constants.SEED_MAP, STAMINA, SYSTEM
├── core.exceptions (统一异常)
└── game_engine (体力恢复、成熟判断)
```

> **注**：
> - `ItemRepo` 不存在，物品操作由 `FarmRepo` 的 `add_item` / `remove_item` 方法处理
> - `StealLog` 由 service 层直接写入，不经过独立的 repository
> - 偷菜冷却和每日计数查询在 service 内部完成（`_check_cooldown` / `_count_today_steals`）
> - 通知系统尚未实现
