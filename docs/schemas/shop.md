# 商店模块 Pydantic Schema

> 定义商店系统（购买种子、浏览商店）的 Pydantic 数据验证模型。  
> 对应代码文件：`app/schemas/shop.py`  
> 出售作物由 `FarmService.harvest()` 处理，其 Schema 定义在 `schemas/farm.md`（`HarvestResult`）。

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **购买请求校验** | 校验购买种子的种子类型和数量 |
| **商店列表响应** | 返回可购买的种子清单和用户金币 |
| **交易结果响应** | 返回购买后的金币变化 |

> **注**：出售作物不在本模块处理，通过 `POST /api/farm/harvest` 端点完成（见 `schemas/farm.md` 的 `HarvestResult`）。

---

## 2. Schema 列表

| 类名 | 用途 | 方向 | 字段数 |
|------|------|------|--------|
| `BuySeedRequest` | 购买种子请求 | 请求 | 2 |
| `BuySeedResponse` | 购买结果 | 响应 | 4 |
| `ShopItem` | 商店商品条目 | 响应 | 6 |
| `ShopListResponse` | 商店列表 | 响应 | 2 |

---

## 3. 字段校验规则

| Schema | 字段 | 类型 | 规则 |
|--------|------|------|------|
| `BuySeedRequest` | `seed_type` | str | `min_length=1, max_length=32`, 必须在 `SEED_MAP` 中 |
| `BuySeedRequest` | `quantity` | int | `ge=1, le=99` |

---

## 4. 完整 Python 实现

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import SEEDS


class BuySeedRequest(BaseModel):
    """购买种子请求体"""
    seed_type: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="种子类型（如 wheat, carrot）",
    )
    quantity: int = Field(
        ...,
        ge=1,
        le=99,
        description="购买数量",
    )

    @field_validator("seed_type")
    @classmethod
    def check_seed_type(cls, v: str) -> str:
        if v not in SEEDS:
            raise ValueError(f"未知的种子类型: {v}")
        return v


class BuySeedResponse(BaseModel):
    """购买结果"""
    seed_type: str
    quantity: int
    total_cost: int
    remaining_coins: int


class ShopItem(BaseModel):
    """商店商品条目"""
    model_config = ConfigDict(from_attributes=True)

    seed_type: str
    name: str
    buy_price: int
    sell_price: int
    unlock_level: int
    grow_time: int  # 秒


class ShopListResponse(BaseModel):
    """商店列表"""
    seeds: list[ShopItem]
    user_coins: int
```

---

## 5. 与 routes/shop.md 集成

```python
from fastapi import APIRouter, Depends
from app.schemas.shop import (
    BuySeedRequest, BuySeedResponse,
    ShopListResponse,
)

router = APIRouter(prefix="/shop", tags=["商店"])


@router.get("/seeds", response_model=ShopListResponse)
async def shop_seeds(
    svc: ShopService = Depends(_get_service),
):
    ...


@router.post("/buy", response_model=BuySeedResponse)
async def buy_seeds(
    body: BuySeedRequest,
    svc: ShopService = Depends(_get_service),
):
    ...
```

---

## 6. 设计决策

### 为什么没有 SellCropRequest / SellCropResponse？

出售作物由 `FarmService.harvest()` 处理——收获即出售，直接按 `sell_price` 增加金币。
这避免了单独 "sell" 端点和 `FarmService` 操作同一作物的事务冲突。
收获结果由 `schemas/farm.md` 的 `HarvestResult` 定义。

### 价格从哪来？

购买价和出售价来自 `core/constants.py` 的 `SEED_MAP` 配置。`ShopService` 在 `ShopListResponse` 中从 `SEED_MAP` 组装商品列表，不查询独立的商店表。

### 字段命名

请求体使用 `seed_type`（而非 `crop_type`），与 `FarmService.plant()` 的 `seed_type` 参数保持一致。
