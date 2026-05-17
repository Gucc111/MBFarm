# Farm Schemas — 农场操作校验模型

## 1. 模块职责

本模块定义了 MB Farm 农场操作相关的 Pydantic v2 数据校验 Schema，涵盖：

- **种植 (`PlantRequest`)** — 校验地块索引、种子类型合法性
- **收获 (`HarvestRequest`)** — 校验地块索引
- **浇水 (`WaterRequest`)** — 校验地块索引
- **作物响应 (`CropResponse`)** — 封装单块地的作物状态
- **地块响应 (`PlotResponse`)** — 封装单块地完整信息（含作物）
- **农场响应 (`FarmResponse`)** — 封装用户农场全局状态

所有 Schema 均位于 `app/schemas/farm.py`，通过 `from app.schemas.farm import *` 导入后用于 `routes/farm.py` 的路由参数校验。

---

## 2. Schema 总览

| 类名 | 用途 | 类型 | 字段数 |
|------|------|------|--------|
| `PlantRequest` | 种植请求体 | Request Body | 2 |
| `HarvestRequest` | 收获请求体 | Request Body | 1 |
| `WaterRequest` | 浇水请求体 | Request Body | 1 |
| `CropResponse` | 作物状态响应 | Response Body | 8 |
| `PlotResponse` | 地块完整响应 | Response Body | 5 |
| `FarmResponse` | 农场全局响应 | Response Body | 5 |

---

## 3. 字段校验规则

### 3.1 `PlantRequest`

| 字段 | 类型 | 校验规则 |
|------|------|----------|
| `plot_index` | `int` | `1 ≤ plot_index ≤ 25` |
| `seed_type` | `str` | 长度 1–32；必须存在于 `SEEDS` 常量中 |

### 3.2 `HarvestRequest`

| 字段 | 类型 | 校验规则 |
|------|------|----------|
| `plot_index` | `int` | `1 ≤ plot_index ≤ 25` |

### 3.3 `WaterRequest`

| 字段 | 类型 | 校验规则 |
|------|------|----------|
| `plot_index` | `int` | `1 ≤ plot_index ≤ 25` |

### 3.4 `CropResponse`

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | `int` | — | 作物记录主键 |
| `seed_type` | `str` | — | 种子类型标识 |
| `seed_name` | `str` | `""` | 种子中文名 |
| `plant_time` | `datetime` | — | 种植时间 |
| `duration` | `int` | — | 成熟所需浇水次数 |
| `is_mature` | `bool` | `False` | 是否已成熟（计算字段） |
| `mature_at` | `Optional[datetime]` | `None` | 预计成熟时间（计算字段） |
| `growth_stage` | `str` | `"seedling"` | 生长阶段（计算字段） |

### 3.5 `PlotResponse`

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | `int` | — | 地块主键 |
| `index` | `int` | — | 地块编号 (1–25) |
| `level` | `int` | — | 地块等级 |
| `crop` | `Optional[CropResponse]` | `None` | 当前种植的作物 |
| `watered_times` | `int` | `0` | 已浇水次数 |

### 3.6 `FarmResponse`

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `user_id` | `int` | — | 用户 ID |
| `plots` | `list[PlotResponse]` | — | 全部 25 块地 |
| `stamina` | `int` | `100` | 剩余体力 |
| `coins` | `int` | `0` | 金币余额 |
| `level` | `int` | `1` | 用户等级 |

---

## 4. 完整 Python 实现

```python
from pydantic import BaseModel, Field, field_validator, computed_field
from datetime import datetime
from typing import Optional


class PlantRequest(BaseModel):
    """种植操作请求体"""
    plot_index: int = Field(ge=1, le=25, description="地块编号 1-25")
    seed_type: str = Field(min_length=1, max_length=32, description="种子类型标识")

    @field_validator("seed_type")
    @classmethod
    def check_seed(cls, v: str) -> str:
        from app.core.constants import SEEDS
        if v not in SEEDS:
            raise ValueError(f"未知的种子类型: {v}")
        return v


class HarvestRequest(BaseModel):
    """收获操作请求体"""
    plot_index: int = Field(ge=1, le=25, description="地块编号 1-25")


class WaterRequest(BaseModel):
    """浇水操作请求体"""
    plot_index: int = Field(ge=1, le=25, description="地块编号 1-25")


class CropResponse(BaseModel):
    """作物状态响应体"""
    model_config = {"from_attributes": True}

    id: int
    seed_type: str
    seed_name: str = ""
    plant_time: datetime
    duration: int
    is_mature: bool = False
    mature_at: Optional[datetime] = None
    growth_stage: str = "seedling"


class PlotResponse(BaseModel):
    """地块完整响应体"""
    model_config = {"from_attributes": True}

    id: int
    index: int
    level: int
    crop: Optional[CropResponse] = None
    watered_times: int = 0


class FarmResponse(BaseModel):
    """农场全局响应体"""
    model_config = {"from_attributes": True}

    user_id: int
    plots: list[PlotResponse]
    stamina: int = 100
    coins: int = 0
    level: int = 1
```

---

## 5. 与 routes/farm.md 集成

`app/routes/farm.py` 中各端点引用方式：

| 端点 | 方法 | Schema 绑定 |
|------|------|-------------|
| `POST /api/farm/plant` | `plant_crops()` | `body: PlantRequest` |
| `POST /api/farm/harvest` | `harvest_crops()` | `body: HarvestRequest` |
| `POST /api/farm/water` | `water_crops()` | `body: WaterRequest` |
| `GET /api/farm/status` | `get_farm_status()` | `response_model=FarmResponse` |

路由层无需手动校验，Pydantic 自动完成：
- 请求体解析与校验 → 失败返回 **422 Unprocessable Entity**
- 响应体验证 → 失败触发 **500 Internal Server Error**

---

## 6. 计算字段说明

`CropResponse` 中的三个字段为**由 Service 层动态计算**，非持久化到数据库：

| 字段 | 计算逻辑 |
|------|----------|
| `is_mature` | `crop.watered_times >= crop.duration` |
| `mature_at` | `plant_time + duration * water_interval`（`water_interval` 由种子配置决定） |
| `growth_stage` | 根据 `watered_times / duration` 比例返回阶段标签：`seedling` / `growing` / `mature` |

这些字段由 `app/services/farm_service.py` 在 `build_crop_response()` 中统一填充，确保数据一致性。
