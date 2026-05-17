# Farm Schemas — 农场操作校验模型

## 模块职责

本模块定义了 MB Farm 农场操作相关的 Pydantic v2 数据校验 Schema，涵盖种植、收获、浇水、解锁、农场信息等操作。

所有 Schema 均位于 `app/schemas/farm.py`。

---

## Schema 总览

| 类名 | 用途 | 类型 |
|------|------|------|
| `PlantRequest` | 种植请求体 | Request |
| `HarvestRequest` | 收获请求体 | Request |
| `WaterRequest` | 浇水请求体 | Request |
| `SeedInfo` | 种子信息 | Response |
| `CropInfo` | 地块上的作物信息 | Response |
| `PlotResponse` | 单个地块响应 | Response |
| `UserFarmInfo` | 农场用户信息 | Response |
| `FarmInfoResponse` | 农场完整信息响应 | Response |
| `HarvestResult` | 收获结果 | Response |
| `UnlockResult` | 解锁地块结果 | Response |
| `WaterResult` | 浇水结果 | Response |

---

## 字段说明

### PlantRequest

| 字段 | 类型 | 校验 | 说明 |
|------|------|------|------|
| `plot_index` | `int` | `1 ≤ x ≤ 25` | 地块编号 (1-based) |
| `seed_type` | `str` | 长度 1–32 | 种子类型 (如 `wheat`, `carrot`) |

### WaterRequest

| 字段 | 类型 | 校验 | 说明 |
|------|------|------|------|
| `plot_index` | `int` | `1 ≤ x ≤ 25` | 地块编号 (1-based) |

### HarvestRequest

| 字段 | 类型 | 校验 | 说明 |
|------|------|------|------|
| `plot_index` | `int` | `1 ≤ x ≤ 25` | 地块编号 (1-based) |

### SeedInfo

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 种子唯一标识 |
| `name` | `str` | 种子中文名 |
| `buy_price` | `int` | 购买价格 |
| `sell_price` | `int` | 出售价格 |
| `grow_time` | `int` | 基础生长时间（秒） |
| `xp_reward` | `int` | 经验值奖励 |
| `unlock_level` | `int` | 解锁等级 |
| `water_bonus` | `int` | 每次浇水减少的生长时间（秒） |

### CropInfo

| 字段 | 类型 | 说明 |
|------|------|------|
| `seed_type` | `str` | 种子类型标识 |
| `seed_name` | `str` | 种子中文名 |
| `plant_time` | `datetime` | 种植时间（UTC） |
| `watered_times` | `int` | 已浇水次数 |
| `is_mature` | `bool` | 是否已成熟（由 `game_engine.is_mature()` 计算） |
| `mature_at` | `datetime \| None` | 预计成熟时间（由 `game_engine.get_mature_at()` 计算） |
| `growth_stage` | `str` | 生长阶段：`"seedling"` / `"growing"` / `"almost_mature"` / `"mature"` |

### PlotResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| `index` | `int` | 地块编号 (1-based) |
| `level` | `int` | 地块等级 |
| `crop` | `CropInfo \| None` | 当前种植的作物（空地块为 `None`） |
| `watered_times` | `int` | 已浇水次数 |
| `planted_at` | `datetime \| None` | 种植时间 |

**配置**: `model_config = ConfigDict(from_attributes=True)`

### UserFarmInfo

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `int` | 用户 ID |
| `username` | `str` | 用户名 |
| `coins` | `int` | 金币余额 |
| `stamina` | `int` | 当前体力 |
| `xp` | `int` | 累计经验值 |
| `level` | `int` | 用户等级 |

### FarmInfoResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| `user` | `UserFarmInfo` | 用户农场信息 |
| `plots` | `list[PlotResponse]` | 全部地块 |
| `max_plots` | `int` | 最大可解锁地块数 |

### HarvestResult

| 字段 | 类型 | 说明 |
|------|------|------|
| `seed_type` | `str` | 收获的种子类型 |
| `seed_name` | `str` | 种子中文名 |
| `xp_reward` | `int` | 获得经验值 |
| `coins_earned` | `int` | 获得金币 |
| `new_level` | `int` | 收获后等级 |
| `xp_before` | `int` | 收获前经验值 |
| `xp_after` | `int` | 收获后经验值 |

### UnlockResult

| 字段 | 类型 | 说明 |
|------|------|------|
| `plot_index` | `int` | 新解锁的地块编号 |
| `remaining_coins` | `int` | 剩余金币 |
| `total_plots` | `int` | 总地块数 |

### WaterResult

| 字段 | 类型 | 说明 |
|------|------|------|
| `plot_index` | `int` | 地块编号 |
| `watered_times` | `int` | 浇水次数 |
| `mature_at` | `str \| None` | 预计成熟时间（ISO 格式） |
| `growth_stage` | `str` | 生长阶段 |

---

## 完整 Python 实现

```python
"""Pydantic schemas for farm endpoints (plant, harvest, water, unlock, status)."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class PlantRequest(BaseModel):
    plot_index: int = Field(..., ge=1, le=25, description="地块编号 (1-based)")
    seed_type: str = Field(..., min_length=1, max_length=32, description="种子类型 (如 wheat, carrot)")


class WaterRequest(BaseModel):
    plot_index: int = Field(..., ge=1, le=25, description="地块编号 (1-based)")


class HarvestRequest(BaseModel):
    plot_index: int = Field(..., ge=1, le=25, description="地块编号 (1-based)")


class SeedInfo(BaseModel):
    id: str
    name: str
    buy_price: int
    sell_price: int
    grow_time: int
    xp_reward: int
    unlock_level: int
    water_bonus: int


class CropInfo(BaseModel):
    seed_type: str
    seed_name: str
    plant_time: datetime
    watered_times: int
    is_mature: bool
    mature_at: datetime | None = None
    growth_stage: str


class PlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    index: int
    level: int
    crop: CropInfo | None = None
    watered_times: int
    planted_at: datetime | None = None


class UserFarmInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    coins: int
    stamina: int
    xp: int
    level: int


class FarmInfoResponse(BaseModel):
    user: UserFarmInfo
    plots: list[PlotResponse]
    max_plots: int = Field(ge=1, description="最大可解锁地块数")


class HarvestResult(BaseModel):
    seed_type: str
    seed_name: str
    xp_reward: int
    coins_earned: int
    new_level: int
    xp_before: int
    xp_after: int


class UnlockResult(BaseModel):
    plot_index: int
    remaining_coins: int
    total_plots: int


class WaterResult(BaseModel):
    plot_index: int
    watered_times: int
    mature_at: datetime | None = None
    growth_stage: str
```

---

## 与 routes 集成

| 端点 | 方法 | 请求 Schema | 响应 Schema |
|------|------|-------------|-------------|
| `POST /api/farm/plant` | `plant()` | `PlantRequest` | `PlotResponse` |
| `POST /api/farm/water` | `water()` | `WaterRequest` | `WaterResult` |
| `POST /api/farm/harvest` | `harvest()` | `HarvestRequest` | `HarvestResult` |
| `POST /api/farm/unlock` | `unlock_plot()` | — | `UnlockResult` |
| `GET /api/farm/info` | `farm_info()` | — | `FarmInfoResponse` |
