# 农场服务 (FarmService)

> 农场核心业务逻辑：种植、收获、浇水、解锁地块、体力管理。  
> 对应代码文件：`app/services/farm.py`

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **种植** | 校验地块 → 消耗种子 → 消耗体力 → 创建作物记录 |
| **收获** | 校验成熟 → 标记收获 → 增加 XP → 检查升级 |
| **浇水** | 校验地块 → 消耗体力 → 增加浇水次数 → 缩短成熟时间 |
| **解锁地块** | 校验权限 → 消耗金币 → 解锁新地块 |
| **体力管理** | 每次操作前恢复离线体力、校验体力充足 |

---

## 2. 设计决策

### 异常处理

农场服务统一使用 `core/exceptions.md` 中定义的 `AppError` 子类，不定义自定义异常类：

| 业务场景 | 异常类 | HTTP 状态码 |
|----------|--------|-------------|
| 地块被锁定 | `AppValidationError("地块未解锁")` | 422 |
| 地块已有作物 | `ConflictError("地块已有作物")` | 409 |
| 地块为空 | `NotFoundError("地块没有作物")` | 404 |
| 作物未成熟 | `AppValidationError("作物尚未成熟")` | 422 |
| 体力不足 | `AppValidationError("体力不足")` | 422 |
| 种子不足 | `AppValidationError("种子不足")` | 422 |

### 作物配置来源

作物配置来自 `core/constants.py` 的 `SEEDS` 字典，**不在 service 中硬编码**。

### 体力管理流程

每次操作前：
1. 通过 `game_engine.restore_stamina()` 计算离线恢复后的体力
2. 校验体力是否足够
3. 扣除操作消耗的体力
4. 更新 `user.last_active_at` 和 `user.stamina`

---

## 3. 方法列表

| 方法 | 参数 | 返回值 | 异常 |
|------|------|--------|------|
| `plant(user_id, plot_index, seed_type)` | — | `Crop` | 422/409 |
| `harvest(user_id, plot_index)` | — | `dict` (crop_type, xp, coins_delta) | 404/422 |
| `water(user_id, plot_index)` | — | `Crop` | 404/422 |
| `unlock_plot(user_id)` | — | `Plot` | 422 |
| `get_farm_info(user_id)` | — | `dict` (plots, stamina, coins) | — |

---

## 4. 完整 Python 实现

```python
"""Farm service — business logic for planting, harvesting, watering, and plot management."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SEEDS, STAMINA, FARM, USER_DEFAULTS
from app.core.exceptions import (
    AppValidationError,
    ConflictError,
    NotFoundError,
)
from app.services.game_engine import restore_stamina, is_mature, get_mature_at, calc_level_from_xp
from app.repositories.farm_repo import FarmRepo
from app.repositories.item_repo import ItemRepo
from app.repositories.user_repo import UserRepository
from app.models.farm import Crop, Plot


class FarmService:
    """农场核心业务逻辑。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.farm_repo = FarmRepo(db)
        self.item_repo = ItemRepo(db)
        self.user_repo = UserRepository(db)

    # ------------------------------------------------------------------
    # 体力管理
    # ------------------------------------------------------------------

    async def _restore_and_check_stamina(self, user_id: int, cost: int) -> None:
        """恢复离线体力并校验是否足够。"""
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("用户不存在")

        # 恢复离线体力
        if user.last_active_at is not None:
            user.stamina = restore_stamina(
                current_stamina=user.stamina,
                last_active=user.last_active_at,
                max_stamina=STAMINA.max_value,
                restore_per_minute=STAMINA.restore_per_minute,
            )

        if user.stamina < cost:
            raise AppValidationError(
                f"体力不足（需要 {cost}，当前 {user.stamina}）"
            )

        user.stamina -= cost
        user.last_active_at = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # 种植
    # ------------------------------------------------------------------

    async def plant(self, user_id: int, plot_index: int, seed_type: str) -> Crop:
        """播种：校验地块 → 消耗种子 → 消耗体力 → 创建作物。"""
        seed_config = SEEDS.get(seed_type)
        if seed_config is None:
            raise AppValidationError(f"未知的种子类型: {seed_type}")

        # 校验等级
        user = await self.user_repo.get_by_id(user_id)
        if user.level < seed_config.unlock_level:
            raise AppValidationError(
                f"需要等级 {seed_config.unlock_level} 才能种植 {seed_config.name}"
            )

        # 校验地块
        plot = await self.farm_repo.get_plot_by_index(user_id, plot_index)
        if plot is None:
            raise NotFoundError("地块不存在")
        if plot.crop_id is not None:
            raise ConflictError("地块已有作物")

        # 消耗种子
        ok = await self.item_repo.remove_item(user_id, "seed", seed_type, quantity=1)
        if not ok:
            raise AppValidationError(f"种子不足: {seed_config.name}")

        # 消耗体力
        await self._restore_and_check_stamina(user_id, STAMINA.cost_plant)

        # 种植
        return await self.farm_repo.plant_crop(
            plot_id=plot.id,
            user_id=user_id,
            seed_type=seed_type,
            duration=seed_config.grow_time,
        )

    # ------------------------------------------------------------------
    # 收获
    # ------------------------------------------------------------------

    async def harvest(self, user_id: int, plot_index: int) -> dict:
        """收获：校验成熟 → 标记收获 → 增加 XP/金币。"""
        plot = await self.farm_repo.get_plot_by_index(user_id, plot_index)
        if plot is None:
            raise NotFoundError("地块不存在")

        crop = await self.farm_repo.get_crop(plot.crop_id)
        if crop is None:
            raise NotFoundError("地块没有作物")

        seed_config = SEEDS.get(crop.seed_type)
        if not is_mature(crop.plant_time, crop.duration, crop.watered_times, seed_config.water_bonus):
            raise AppValidationError("作物尚未成熟")

        # 收获：清除地块上的作物
        await self.farm_repo.harvest_crop(plot.id, user_id)

        # 增加 XP 和金币
        user = await self.user_repo.get_by_id(user_id)
        user.xp += seed_config.xp_reward
        user.coins += seed_config.sell_price

        # 检查升级
        new_level = calc_level_from_xp(user.xp)
        if new_level > user.level:
            user.level = new_level

        user.last_active_at = datetime.now(timezone.utc)
        await self.db.flush()

        return {
            "seed_type": crop.seed_type,
            "seed_name": seed_config.name,
            "xp_reward": seed_config.xp_reward,
            "coins_earned": seed_config.sell_price,
            "new_level": user.level,
        }

    # ------------------------------------------------------------------
    # 浇水
    # ------------------------------------------------------------------

    async def water(self, user_id: int, plot_index: int) -> dict:
        """浇水：校验地块 → 消耗体力 → 增加浇水次数。"""
        plot = await self.farm_repo.get_plot_by_index(user_id, plot_index)
        if plot is None:
            raise NotFoundError("地块不存在")
        if plot.crop_id is None:
            raise NotFoundError("地块没有作物")

        crop = await self.farm_repo.get_crop(plot.crop_id)
        seed_config = SEEDS.get(crop.seed_type)

        if is_mature(crop.plant_time, crop.duration, crop.watered_times, seed_config.water_bonus):
            raise AppValidationError("作物已经成熟，无需浇水")

        # 消耗体力
        await self._restore_and_check_stamina(user_id, STAMINA.cost_water)

        # 浇水
        await self.farm_repo.water_crop(crop.id, user_id)

        mature_at = get_mature_at(
            crop.plant_time, crop.duration, crop.watered_times + 1, seed_config.water_bonus
        )

        return {
            "plot_index": plot_index,
            "watered_times": crop.watered_times + 1,
            "mature_at": mature_at.isoformat(),
        }

    # ------------------------------------------------------------------
    # 解锁地块
    # ------------------------------------------------------------------

    async def unlock_plot(self, user_id: int) -> dict:
        """解锁新地块。"""
        user = await self.user_repo.get_by_id(user_id)

        unlocked_count = await self.farm_repo.count_unlocked_plots(user_id)
        if unlocked_count >= FARM.max_plots:
            raise AppValidationError("已达到最大地块数")

        cost = FARM.unlock_cost_per_plot
        if user.coins < cost:
            raise AppValidationError(f"金币不足（需要 {cost}，当前 {user.coins}）")

        user.coins -= cost
        new_plot = await self.farm_repo.create_plot(user_id, unlocked_count)
        user.last_active_at = datetime.now(timezone.utc)
        await self.db.flush()

        return {
            "plot_index": new_plot.index,
            "remaining_coins": user.coins,
            "total_plots": unlocked_count + 1,
        }

    # ------------------------------------------------------------------
    # 农场信息
    # ------------------------------------------------------------------

    async def get_farm_info(self, user_id: int) -> dict:
        """获取农场完整信息（页面渲染用）。"""
        user = await self.user_repo.get_by_id(user_id)

        # 恢复离线体力
        if user.last_active_at is not None:
            user.stamina = restore_stamina(
                current_stamina=user.stamina,
                last_active=user.last_active_at,
                max_stamina=STAMINA.max_value,
                restore_per_minute=STAMINA.restore_per_minute,
            )

        plots = await self.farm_repo.get_user_plots(user_id)

        return {
            "user_id": user_id,
            "plots": plots,
            "stamina": user.stamina,
            "coins": user.coins,
            "level": user.level,
            "xp": user.xp,
        }
```

---

## 5. 使用方式

```python
from app.services.farm import FarmService

svc = FarmService(db)

# 种植
crop = await svc.plant(user_id=5, plot_index=1, seed_type="wheat")

# 收获
result = await svc.harvest(user_id=5, plot_index=1)
# → {"seed_type": "wheat", "xp_reward": 5, "coins_earned": 18, "new_level": 1}

# 浇水
result = await svc.water(user_id=5, plot_index=1)
# → {"plot_index": 1, "watered_times": 1, "mature_at": "2024-01-15T10:28:00+00:00"}

# 解锁地块
result = await svc.unlock_plot(user_id=5)
# → {"plot_index": 9, "remaining_coins": 300, "total_plots": 10}
```

---

## 6. 依赖关系

```
FarmService
├── FarmRepo (地块/作物 CRUD)
├── ItemRepo (种子消耗)
├── UserRepository (用户金币/XP/体力)
├── core.constants.SEEDS (作物配置)
├── core.constants.STAMINA (体力配置)
├── core.constants.FARM (地块配置)
├── core.exceptions (统一异常)
└── game_engine (体力恢复、成熟判断、等级计算)
```
