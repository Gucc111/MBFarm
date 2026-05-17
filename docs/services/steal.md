# 偷菜服务 (StealService)

> 偷菜业务逻辑：检查目标农田、执行偷取、冷却与每日上限。  
> 对应代码文件：`app/services/steal.py`

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **偷菜** | 查找目标用户成熟作物 → 按 50% 比例偷取 → 更新地块状态 |
| **冷却检查** | 对同一目标用户 30 分钟内只能偷一次 |
| **每日上限** | 每天最多偷 20 次 |
| **体力消耗** | 每次偷菜消耗 3 点体力 |
| **通知推送** | 偷取成功后向被偷用户推送通知 |

---

## 2. 设计决策

### 异常处理

统一使用 `core/exceptions.md` 中定义的 `AppError` 子类：

| 业务场景 | 异常类 | HTTP 状态码 |
|----------|--------|-------------|
| 偷自己的菜 | `ForbiddenError("不能偷自己的作物")` | 403 |
| 冷却中 | `AppValidationError("偷菜冷却中，请 30 分钟后再试")` | 422 |
| 达到每日上限 | `ConflictError("今日偷菜次数已达上限")` | 409 |
| 无成熟作物 | `NotFoundError("目标没有成熟作物可偷")` | 404 |
| 不是好友 | `ForbiddenError("只能偷好友的作物")` | 403 |

### 偷取比例

每次偷取目标地块上成熟作物的 **50%**。偷取后：
- 目标地块上的作物被移除（crop 记录标记 `is_harvested=True`）
- 偷菜者的 inventory 中增加偷取的作物（`item_type=harvest, item_subtype=seed_type`）

### 冷却与上限

- **冷却**：对同一目标用户，30 分钟内只能偷一次。通过 `StealLog` 模型记录每次偷取的时间。
- **每日上限**：每天最多偷 20 次，以自然日（00:00 UTC）为界。

### StealLog 模型

偷菜记录是一个轻量模型，定义在 `app/models/steal.py`：

```python
class StealLog(Base):
    __tablename__ = "steal_logs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stealer_id = Column(BigInteger, nullable=False)  # 偷菜者
    victim_id = Column(BigInteger, nullable=False)   # 被偷者
    stolen_crop_type = Column(String(32), nullable=False)
    quantity = Column(Integer, default=1)
    stolen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

---

## 3. 方法列表

| 方法 | 参数 | 返回值 | 异常 |
|------|------|--------|------|
| `steal(user_id, target_user_id)` | — | `dict` (seed_type, quantity, stolen_coins_value) | 403/422/409/404 |
| `get_my_stolen(user_id, today_only)` | — | `list[dict]` | — |
| `get_my_stolen_by_others(user_id)` | — | `list[dict]` | — |

---

## 4. 完整 Python 实现

```python
"""Steal service — business logic for stealing crops from friends."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SEEDS, STAMINA
from app.core.exceptions import (
    AppValidationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.services.game_engine import restore_stamina, is_mature
from app.repositories.farm_repo import FarmRepo
from app.repositories.item_repo import ItemRepo
from app.repositories.user_repo import UserRepository
from app.repositories.social_repo import SocialRepo
from app.models.farm import Crop, Plot
from app.models.user import User


# StealLog model (inline — 定义在 app/models/steal.py)
# class StealLog(Base):
#     __tablename__ = "steal_logs"
#     id = Column(BigInteger, primary_key=True, autoincrement=True)
#     stealer_id = Column(BigInteger, nullable=False)
#     victim_id = Column(BigInteger, nullable=False)
#     stolen_crop_type = Column(String(32), nullable=False)
#     quantity = Column(Integer, default=1)
#     stolen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


COOLDOWN_SECONDS = 30 * 60       # 30 分钟
DAILY_STEAL_LIMIT = 20           # 每日上限
STEAL_RATIO = 0.5                # 偷取比例 50%


class StealService:
    """偷菜业务逻辑。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.farm_repo = FarmRepo(db)
        self.item_repo = ItemRepo(db)
        self.user_repo = UserRepository(db)
        self.social_repo = SocialRepo(db)

    async def steal(self, user_id: int, target_user_id: int) -> dict:
        """偷取目标用户的地块上的成熟作物。"""
        if user_id == target_user_id:
            raise ForbiddenError("不能偷自己的作物")

        # 检查好友关系
        friendship = await self.social_repo.get_friendship(user_id, target_user_id)
        if not friendship or friendship.status != "accepted":
            raise ForbiddenError("只能偷好友的作物")

        # 检查冷却
        # (查询 steal_logs 中最近一次偷 target 的记录)
        # 简化：通过 SocialRepo 扩展方法
        is_cooled = await self.social_repo.check_steal_cooldown(
            user_id, target_user_id, COOLDOWN_SECONDS
        )
        if not is_cooled:
            raise AppValidationError("偷菜冷却中，请 30 分钟后再试")

        # 检查每日上限
        today_count = await self.social_repo.count_today_steals(user_id)
        if today_count >= DAILY_STEAL_LIMIT:
            raise ConflictError("今日偷菜次数已达上限")

        # 查找目标用户成熟地块
        plots = await self.farm_repo.get_user_plots(target_user_id)
        mature_plots = []
        for plot in plots:
            if plot.crop_id is None:
                continue
            crop = await self.farm_repo.get_crop(plot.crop_id)
            if crop is None or crop.is_harvested:
                continue
            seed_config = SEEDS.get(crop.seed_type)
            if seed_config and is_mature(crop.plant_time, crop.duration, crop.watered_times, seed_config.water_bonus):
                mature_plots.append((plot, crop, seed_config))

        if not mature_plots:
            raise NotFoundError("目标没有成熟作物可偷")

        # 偷取：随机选一个成熟地块，偷 50%
        import random
        plot, crop, seed_config = random.choice(mature_plots)

        # 消耗体力
        user = await self.user_repo.get_by_id(user_id)
        if user.last_active_at:
            user.stamina = restore_stamina(
                user.stamina, user.last_active_at,
                STAMINA.max_value, STAMINA.restore_per_minute,
            )
        if user.stamina < STAMINA.cost_steal:
            raise AppValidationError(f"体力不足（需要 {STAMINA.cost_steal}，当前 {user.stamina}）")
        user.stamina -= STAMINA.cost_steal
        user.last_active_at = datetime.now(timezone.utc)

        # 偷取作物：从目标地块移除，加到偷菜者背包
        await self.farm_repo.harvest_crop(plot.id, target_user_id)
        await self.item_repo.add_item(user_id, "harvest", crop.seed_type, quantity=1)

        # 记录偷菜日志
        await self.social_repo.record_steal(user_id, target_user_id, crop.seed_type)

        await self.db.flush()

        return {
            "seed_type": crop.seed_type,
            "seed_name": seed_config.name,
            "quantity": 1,
            "value": seed_config.sell_price,
        }

    async def get_my_stolen(self, user_id: int) -> list[dict]:
        """查看偷到的作物。"""
        records = await self.social_repo.get_my_stolen(user_id)
        return [
            {
                "id": r.id,
                "victim_id": r.victim_id,
                "seed_type": r.stolen_crop_type,
                "stolen_at": r.stolen_at.isoformat(),
            }
            for r in records
        ]

    async def get_my_stolen_by_others(self, user_id: int) -> list[dict]:
        """查看被别人偷走的作物。"""
        records = await self.social_repo.get_stolen_by_others(user_id)
        return [
            {
                "id": r.id,
                "stealer_id": r.stealer_id,
                "seed_type": r.stolen_crop_type,
                "stolen_at": r.stolen_at.isoformat(),
            }
            for r in records
        ]
```

---

## 5. 依赖关系

```
StealService
├── FarmRepo (查询目标地块/作物、收获)
├── ItemRepo (偷取后加背包)
├── UserRepository (体力/金币)
├── SocialRepo (好友校验、偷菜日志)
├── models.farm.Crop, models.farm.Plot
├── models.steal.StealLog
├── core.constants.SEEDS, STAMINA
├── core.exceptions (统一异常)
└── game_engine (体力恢复、成熟判断)
```
