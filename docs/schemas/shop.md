# 商店模块 Pydantic Schema

> 定义商店系统（购买种子、出售作物）的 Pydantic 数据验证模型。  
> 对应代码文件：`app/schemas/shop.py`

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **购买请求校验** | 校验购买种子的种子类型和数量 |
| **出售请求校验** | 校验出售作物的地块索引和数量 |
| **商店列表响应** | 返回可购买的种子清单和用户金币 |
| **交易结果响应** | 返回购买/出售后的金币变化 |

> **注**：偷菜相关的 Schema 定义在 `schemas/steal.md`，不属于本模块。

---

## 2. Schema 列表

| 类名 | 用途 | 方向 | 字段数 |
|------|------|------|--------|
| `BuySeedRequest` | 购买种子请求 | 请求 | 2 |
| `BuySeedResponse` | 购买结果 | 响应 | 4 |
| `SellCropRequest` | 出售作物请求 | 请求 | 2 |
| `SellCropResponse` | 出售结果 | 响应 | 4 |
| `ShopItem` | 商店商品条目 | 响应 | 6 |
| `ShopListResponse` | 商店列表 | 响应 | 2 |

---

## 3. 字段校验规则

| Schema | 字段 | 类型 | 规则 |
|--------|------|------|------|
| `BuySeedRequest` | `seed_type` | str | `min_length=1, max_length=32`, 必须在 SEEDS 常量中 |
| `BuySeedRequest` | `quantity` | int | `ge=1, le=99` |
| `SellCropRequest` | `plot_index` | int | `ge=1, le=25` |
| `SellCropRequest` | `quantity` | int | `ge=1` |

---

## 4. 完整 Python 实现

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import SEEDS


class BuySeedRequest(BaseModel):
    """购买种子请求"""
    seed_type: str = Field(
        min_length=1,
        max_length=32,
        description="种子类型（如 wheat, carrot）",
    )
    quantity: int = Field(
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


class SellCropRequest(BaseModel):
    """出售作物请求"""
    plot_index: int = Field(ge=1, le=25, description="地块索引")
    quantity: int = Field(ge=1, description="出售数量（默认全部）")


class SellCropResponse(BaseModel):
    """出售结果"""
    seed_type: str
    quantity: int
    total_revenue: int
    remaining_coins: int


class ShopItem(BaseModel):
    """商店商品条目"""
    model_config = ConfigDict(from_attributes=True)

    seed_type: str
    name: str
    buy_price: int
    sell_price: int
    unlock_level: int
    grow_time: int        # 秒


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
    SellCropRequest, SellCropResponse,
    ShopListResponse,
)

router = APIRouter(prefix="/shop", tags=["shop"])


@router.get("/", response_model=ShopListResponse)
async def list_seeds(
    user: User = Depends(get_current_user),
    svc: ShopService = Depends(get_shop_service),
):
    ...


@router.post("/buy", response_model=BuySeedResponse)
async def buy_seed(
    payload: BuySeedRequest,
    user: User = Depends(get_current_user),
    svc: ShopService = Depends(get_shop_service),
):
    ...


@router.post("/sell", response_model=SellCropResponse)
async def sell_crop(
    payload: SellCropRequest,
    user: User = Depends(get_current_user),
    svc: ShopService = Depends(get_shop_service),
):
    ...
```

---

## 6. 设计决策

### 为什么不出售用 crop_id 而是 plot_index？

出售操作对应的是地块上的成熟作物。使用 `plot_index` 更直观（用户看到的是第几块地有作物成熟了），而 crop_id 对用户不友好且容易暴露内部结构。

### 价格从哪来？

购买价和出售价来自 `core/constants.py` 的 `SEEDS` 配置。ShopService 在 `ShopListResponse` 中从 SEEDS 组装商品列表，不查询独立的商店表。
