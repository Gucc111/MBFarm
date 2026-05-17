# 农场服务 (FarmService)

> 农场核心业务逻辑：种植、收获、浇水、解锁地块、体力管理。  
> 对应代码文件：`app/services/farm_service.py`

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **种植** | 校验等级 → 校验地块 → 消耗种子 → 消耗体力 → 创建作物记录 |
| **收获** | 校验成熟 → 标记收获 → 增加 XP/金币 → 检查升级 |
| **浇水** | 校验地块 → 校验未成熟 → 消耗体力 → 增加浇水次数 |
| **解锁地块** | 校验权限 → 消耗金币 → 创建新地块 |
| **体力管理** | 每次操作前恢复离线体力、校验体力充足、扣除操作消耗 |
| **农场信息** | 聚合用户信息 + 地块列表，供页面渲染使用 |

---

## 2. 设计决策

### 用户绑定模式

FarmService 在构造时绑定 `user_id`，所有方法不再接受 `user_id` 参数：

```python
def __init__(self, db: AsyncSession, user_id: int):
    self.db = db
    self.user_id = user_id
    self.farm_repo = FarmRepo(db)
    self.user_repo = UserRepository(db)
```

这确保了每个 FarmService 实例只操作当前认证用户的数据。

### 异常处理

使用 `core/exceptions` 中定义的 `AppError` 子类：

| 业务场景 | 异常类 | HTTP 状态码 |
|----------|--------|-------------|
| 地块被锁定 | `AppValidationError("地块未解锁")` | 422 |
| 地块已有作物 | `ConflictError("地块已有作物")` | 409 |
| 地块为空 | `NotFoundError("地块没有作物")` | 404 |
| 作物未成熟 | `AppValidationError("作物尚未成熟")` | 422 |
| 体力不足 | `AppValidationError("体力不足")` | 422 |
| 种子不足 | `AppValidationError("种子不足")` | 422 |

### 作物配置来源

作物配置来自 `app.core.constants.SEED_MAP` 字典（`SeedConfig` dataclass），**不在 service 中硬编码**。

### 体力管理流程

通过 `_ensure_stamina(cost)` 私有方法统一处理：
1. 获取用户，通过 `game_engine.restore_stamina()` 计算离线恢复后的体力
2. 校验体力是否足够，不足则抛 `AppValidationError`
3. 扣除操作消耗的体力
4. 更新 `user.last_active_at`

---

## 3. 方法列表

| 方法 | 签名 | 返回值 | 异常 |
|------|------|--------|------|
| `plant` | `(plot_index, seed_type)` | `Crop` | 422/409/404 |
| `harvest` | `(plot_index)` | `dict` | 404/422 |
| `water` | `(plot_index)` | `dict` | 404/422 |
| `unlock_plot` | `()` | `dict` | 422 |
| `get_farm_info` | `()` | `dict` (raw data) | — |
| `get_farm_info_response` | `()` | `FarmInfoResponse` (Pydantic) | — |

### 辅助方法

| 方法 | 说明 |
|------|------|
| `_ensure_stamina(cost)` | 恢复体力并校验 |
| `_persist_user(user)` | 将用户变更刷入数据库 |
| `_make_crop_info(crop)` | 从 Crop ORM 构建 `CropInfo` Pydantic 对象 |
| `_make_plot_response(plot)` | 从 Plot ORM 构建 `PlotResponse` |

---

## 4. 完整 Python 实现

```python
"""Farm service — business logic for planting, harvesting, watering, and plot management."""

from datetime import datetime, timezone
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.constants import FARM, SEED_MAP, STAMINA
from app.core.exceptions import AppValidationError, ConflictError, NotFoundError
from app.repositories.farm_repo import FarmRepo
from app.repositories.user_repo import UserRepository
from app.schemas.farm import CropInfo, FarmInfoResponse, PlotResponse, UserFarmInfo
from app.services.game_engine import (
    calc_level_from_xp, calc_growth_stage, get_mature_at, is_mature, restore_stamina,
)
from app.models.farm import Crop, Plot


class FarmService:
    """农场核心业务逻辑。"""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id
        self.farm_repo = FarmRepo(db)
        self.user_repo = UserRepository(db)

    # ── 体力管理 ────────────────────────────────────────────────

    async def _ensure_stamina(self, cost: int) -> None:
        user = await self.user_repo.get_by_id(self.user_id)
        if user is None:
            raise NotFoundError("用户不存在")

        if user.last_active_at is not None:
            user.stamina = restore_stamina(
                current_stamina=user.stamina,
                last_active=user.last_active_at,
                max_stamina=STAMINA.max_value,
                restore_per_minute=STAMINA.regen_per_min,
            )

        if user.stamina < cost:
            raise AppValidationError(f"体力不足（需要 {cost}，当前 {user.stamina}）")

        user.stamina -= cost
        user.last_active_at = datetime.now(timezone.utc)

    async def _persist_user(self, user) -> None:
        user.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

    # ── 种植 ────────────────────────────────────────────────────

    async def plant(self, plot_index: int, seed_type: str) -> Crop:
        seed_config = SEED_MAP.get(seed_type)
        if seed_config is None:
            raise AppValidationError(f"未知的种子类型: {seed_type}")

        user = await self.user_repo.get_by_id(self.user_id)
        if user.level < seed_config.unlock_level:
            raise AppValidationError(f"需要等级 {seed_config.unlock_level} 才能种植 {seed_config.name}")

        plot = await self.farm_repo.get_plot_by_index(self.user_id, plot_index)
        if plot is None:
            raise NotFoundError("地块不存在")
        if plot.crop_id is not None:
            raise ConflictError("地块已有作物")

        ok = await self.farm_repo.remove_item(self.user_id, "seed", seed_type, quantity=1)
        if not ok:
            raise AppValidationError(f"种子不足: {seed_config.name}")

        await self._ensure_stamina(STAMINA.plant_cost)

        return await self.farm_repo.plant_crop(
            plot_id=plot.id, user_id=self.user_id,
            seed_type=seed_type, duration=seed_config.grow_time,
        )

    # ── 收获 ────────────────────────────────────────────────────

    async def harvest(self, plot_index: int) -> dict:
        plot = await self.farm_repo.get_plot_by_index(self.user_id, plot_index)
        if plot is None:
            raise NotFoundError("地块不存在")

        crop = await self.farm_repo.get_crop(plot.crop_id)
        if crop is None:
            raise NotFoundError("地块没有作物")

        seed_config = SEED_MAP.get(crop.seed_type)
        if not is_mature(crop.plant_time, crop.duration, crop.watered_times, seed_config.water_bonus):
            raise AppValidationError("作物尚未成熟")

        await self.farm_repo.harvest_crop(plot)

        user = await self.user_repo.get_by_id(self.user_id)
        xp_before = user.xp
        user.xp += seed_config.xp_reward
        user.coins += seed_config.sell_price

        new_level = calc_level_from_xp(user.xp)
        if new_level > user.level:
            user.level = new_level

        user.last_active_at = datetime.now(timezone.utc)
        await self._persist_user(user)

        return {
            "seed_type": crop.seed_type,
            "seed_name": seed_config.name,
            "xp_reward": seed_config.xp_reward,
            "coins_earned": seed_config.sell_price,
            "new_level": new_level,
            "xp_before": xp_before,
            "xp_after": user.xp,
        }

    # ── 浇水 ────────────────────────────────────────────────────

    async def water(self, plot_index: int) -> dict:
        plot = await self.farm_repo.get_plot_by_index(self.user_id, plot_index)
        if plot is None:
            raise NotFoundError("地块不存在")
        if plot.crop_id is None:
            raise NotFoundError("地块没有作物")

        crop = await self.farm_repo.get_crop(plot.crop_id)
        seed_config = SEED_MAP.get(crop.seed_type)

        if is_mature(crop.plant_time, crop.duration, crop.watered_times, seed_config.water_bonus):
            raise AppValidationError("作物已经成熟，无需浇水")

        await self._ensure_stamina(STAMINA.water_cost)
        cropped = await self.farm_repo.water_crop(plot)

        mature_at = None
        if cropped:
            mature_at = get_mature_at(
                cropped.plant_time, cropped.duration,
                cropped.watered_times, seed_config.water_bonus
            )

        return {
            "plot_index": plot_index,
            "watered_times": plot.watered_times,
            "mature_at": mature_at.isoformat() if mature_at else None,
            "growth_stage": calc_growth_stage(
                cropped.plant_time, cropped.duration,
                cropped.watered_times, seed_config.water_bonus,
            ) if cropped else "",
        }

    # ── 解锁地块 ────────────────────────────────────────────────

    async def unlock_plot(self) -> dict:
        user = await self.user_repo.get_by_id(self.user_id)
        unlocked_count = await self.farm_repo.count_unlocked_plots(self.user_id)
        if unlocked_count >= FARM.max_plots:
            raise AppValidationError("已达到最大地块数")

        cost = FARM.plot_upgrade_cost
        if user.coins < cost:
            raise AppValidationError(f"金币不足（需要 {cost}，当前 {user.coins}）")

        user.coins -= cost
        new_plot = await self.farm_repo.create_plot(self.user_id, unlocked_count + 1)
        user.last_active_at = datetime.now(timezone.utc)
        await self._persist_user(user)

        return {
            "plot_index": new_plot.index,
            "remaining_coins": user.coins,
            "total_plots": unlocked_count + 1,
        }

    # ── 农场信息 ────────────────────────────────────────────────

    async def get_farm_info(self) -> dict:
        user = await self.user_repo.get_by_id(self.user_id)
        if user.last_active_at is not None:
            user.stamina = restore_stamina(
                current_stamina=user.stamina,
                last_active=user.last_active_at,
                max_stamina=STAMINA.max_value,
                restore_per_minute=STAMINA.regen_per_min,
            )
        plots = await self.farm_repo.get_user_plots(self.user_id)
        return {
            "user_id": self.user_id,
            "plots": plots,
            "stamina": user.stamina,
            "coins": user.coins,
            "level": user.level,
            "xp": user.xp,
        }

    async def get_farm_info_response(self) -> FarmInfoResponse:
        info = await self.get_farm_info()
        plots_resp = [self._make_plot_response(p) for p in info["plots"]]
        user_resp = UserFarmInfo(
            id=info["user_id"], username="", coins=info["coins"],
            stamina=info["stamina"], xp=info["xp"], level=info["level"],
        )
        return FarmInfoResponse(user=user_resp, plots=plots_resp, max_plots=FARM.max_plots)
```

---

## 5. 依赖注入

通过 `farm_service_dep` 依赖注入：

```python
def farm_service_dep(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FarmService:
    return FarmService(db, user.id)
```

---

## 6. 依赖关系

```
FarmService
├── FarmRepo (地块/作物 CRUD + 背包操作)
├── UserRepository (用户金币/XP/体力)
├── core.constants.SEED_MAP (作物配置)
├── core.constants.STAMINA (体力配置)
├── core.constants.FARM (地块配置)
├── core.exceptions (统一异常)
├── schemas.farm (Pydantic response schemas)
└── game_engine (体力恢复、成熟判断、等级计算)
```

---

## 7. 常量属性对照

| 常量 | 属性 | 用途 |
|------|------|------|
| `STAMINA.max_value` | 100 | 最大体力 |
| `STAMINA.regen_per_min` | 1 | 每分钟恢复体力 |
| `STAMINA.plant_cost` | 5 | 种植消耗体力 |
| `STAMINA.harvest_cost` | 3 | 收获消耗体力 |
| `STAMINA.water_cost` | 2 | 浇水消耗体力 |
| `FARM.max_plots` | 25 | 最大地块数 |
| `FARM.plot_upgrade_cost` | 200 | 解锁地块金币消耗 |
| `FARM.initial_plots` | 9 | 初始地块数 |
