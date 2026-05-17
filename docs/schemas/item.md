# item.md — 物品操作校验模型 (Pydantic v2)

## 1. 模块职责

本模块定义了 MB Farm 游戏中与 **物品/商店/背包** 相关的 Pydantic v2 校验模型：

- 种子购买 (`BuySeedRequest`)
- 作物出售 (`SellRequest`)
- 背包物品展示 (`InventoryItemResponse`)
- 商店物品/商城响应 (`ShopItemResponse`, `ShopResponse`)

统一在 `schemas/item.py` 中实现，开启 `from_attributes=True` 以便直接读取 ORM 对象/字典。

---

## 2. Schema 列表

| Schema | 用途 |
|---|---|
| `BuySeedRequest` | POST `/shop/buy` 请求体，购买种子 |
| `SellRequest` | POST `/shop/sell` 请求体，出售作物 |
| `InventoryItemResponse` | 背包中单个物品的响应结构 |
| `ShopItemResponse` | 商城中单个商品的展示信息 |
| `ShopResponse` | 商城页面整体响应（商品列表 + 用户金币） |

---

## 3. 字段校验规则

### BuySeedRequest

| 字段 | 类型 | 校验规则 |
|---|---|---|
| `seed_type` | `str` | 必填，长度 1-64 |
| `quantity` | `int` | 1 ≤ quantity ≤ 99 |

### SellRequest

| 字段 | 类型 | 校验规则 |
|---|---|---|
| `item_subtype` | `str` | 必填，种子/作物类型名 |
| `quantity` | `int` | quantity ≥ 1 |

### InventoryItemResponse

| 字段 | 类型 | 说明 |
|---|---|---|
| `item_type` | `str` | 物品类型 (seed / crop / etc.) |
| `item_subtype` | `str` | 子类型标识 |
| `quantity` | `int` | 持有数量 |
| `item_name` | `str` | 人类可读名称（可由 computed_field 生成） |

### ShopItemResponse

| 字段 | 类型 | 说明 |
|---|---|---|
| `seed_type` | `str` | 种子唯一标识 |
| `name` | `str` | 名称 |
| `buy_price` | `int` | 购买价格 |
| `sell_price` | `int` | 出售价格 |
| `unlock_level` | `int` | 解锁等级 |
| `grow_time` | `int` | 生长时间（秒） |

### ShopResponse

| 字段 | 类型 | 说明 |
|---|---|---|
| `seeds` | `list[ShopItemResponse]` | 全部可购种子 |
| `user_coins` | `int` | 用户当前金币余额 |

---

## 4. 完整 Python 代码

```python
"""
schemas/item.py — 物品 / 商店 / 背包 Pydantic v2 校验模型
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, computed_field


# ──────────────────────────────────────────────
# Request Schemas
# ──────────────────────────────────────────────

class BuySeedRequest(BaseModel):
    """POST /shop/buy 请求体"""

    seed_type: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(..., ge=1, le=99)


class SellRequest(BaseModel):
    """POST /shop/sell 请求体"""

    item_subtype: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(..., ge=1)


# ──────────────────────────────────────────────
# Response Schemas
# ──────────────────────────────────────────────

class InventoryItemResponse(BaseModel):
    """背包中单个物品的响应结构"""

    item_type: str
    item_subtype: str
    quantity: int

    @computed_field
    @property
    def item_name(self) -> str:
        """由 item_type + item_subtype 拼接的人类可读名称"""
        return f"{self.item_type}:{self.item_subtype}"


class ShopItemResponse(BaseModel):
    """商城中单个种子商品的展示信息"""

    seed_type: str
    name: str
    buy_price: int
    sell_price: int
    unlock_level: int
    grow_time: int


class ShopResponse(BaseModel):
    """GET /shop 整体响应"""

    seeds: List[ShopItemResponse]
    user_coins: int