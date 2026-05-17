# Item Schemas — 物品/商店/背包校验模型

> **模块**: `app/schemas/item.py`

## 1. 模块职责

本模块定义了 MB Farm 游戏中与 **物品/商店/背包** 相关的 Pydantic v2 校验模型：

- 种子购买 (`BuySeedRequest`)
- 背包物品展示 (`InventoryItem`)
- 商店物品 (`ShopItem`)
- 商店/背包响应 (`ShopResponse`, `InventoryResponse`)

## 2. Schema 列表

| Schema | 用途 | 类型 |
|--------|------|------|
| `BuySeedRequest` | `POST /api/farm/shop/buy` 请求体 | Request |
| `InventoryItem` | 背包中单个物品 | Response |
| `ShopItem` | 商店中单个商品 | Response |
| `ShopResponse` | 商店种子列表 | Response |
| `InventoryResponse` | 用户背包 + 金币 | Response |

## 3. 字段校验规则

### BuySeedRequest

| 字段 | 类型 | 校验规则 |
|------|------|----------|
| `seed_type` | `str` | 必填，长度 1-32 |
| `quantity` | `int` | 1 ≤ quantity ≤ 99 |

### InventoryItem

| 字段 | 类型 | 说明 |
|------|------|------|
| `item_type` | `str` | 物品类型 (seed / harvest / fertilizer / tool) |
| `item_subtype` | `str` | 子类型标识 |
| `quantity` | `int` | 持有数量 |

### ShopItem

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 种子唯一标识 |
| `name` | `str` | 种子名称 |
| `price` | `int` | 购买价格 |
| `sell_price` | `int` | 出售价格 |
| `grow_time` | `int` | 生长时间（秒） |
| `xp_reward` | `int` | 经验值奖励 |
| `unlock_level` | `int` | 解锁等级 |
| `water_bonus` | `int` | 每次浇水减少的秒数 |

### ShopResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| `seeds` | `list[ShopItem]` | 全部可购种子 |

### InventoryResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| `items` | `list[InventoryItem]` | 背包全部物品 |
| `total_coins` | `int` | 用户当前金币余额 |

## 4. 完整 Python 实现

```python
"""Pydantic schemas for shop/inventory endpoints."""

from pydantic import BaseModel, ConfigDict, Field


class BuySeedRequest(BaseModel):
    seed_type: str = Field(..., min_length=1, max_length=32, description="种子类型")
    quantity: int = Field(..., ge=1, le=99, description="购买数量")


class InventoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    item_type: str
    item_subtype: str
    quantity: int


class ShopItem(BaseModel):
    id: str
    name: str
    price: int
    sell_price: int
    grow_time: int
    xp_reward: int
    unlock_level: int
    water_bonus: int


class ShopResponse(BaseModel):
    seeds: list[ShopItem]


class InventoryResponse(BaseModel):
    items: list[InventoryItem]
    total_coins: int
```

## 5. 与 routes 集成

| 端点 | 方法 | 请求 Schema | 响应 Schema |
|------|------|-------------|-------------|
| `GET /api/farm/shop/seeds` | `shop_seeds()` | — | `ShopResponse` |
| `POST /api/farm/shop/buy` | `buy_seed()` | `BuySeedRequest` | dict (message + remaining_coins) |
| `GET /api/farm/inventory` | `inventory()` | — | `InventoryResponse` |

## 6. 扩展计划

| 阶段 | 扩展内容 |
|------|----------|
| P2 | 出售作物 `SellRequest` Schema |
| P2 | 肥料 expiration 相关 Schema |
