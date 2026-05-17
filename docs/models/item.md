# Item & Inventory Module

## 模块职责

`app/models/item.py` — 定义背包物品（Inventory）数据模型，管理玩家持有的种子、收获物、肥料和工具。

## 设计决策

### 1. 合并存储策略

同用户同类型物品合并到同一行（通过 UNIQUE 约束 + upsert 语义），而非每获得一个物品创建一行。

- **优点**：查询高效（`SELECT quantity WHERE ...`），存储紧凑
- **实现**：添加物品时先查询是否存在，存在则 `quantity += amount`，不存在则 INSERT

### 2. item_type + item_subtype 双字段设计

- **item_type**：区分用途大类（seed / harvest / fertilizer / tool）
- **item_subtype**：具体物品标识（wheat / carrot / ...）

`seed:wheat` 和 `harvest:wheat` 是两条不同的记录，类型不冲突。

### 3. 无过期时间

肥料和工具当前无使用期限设计，后续可扩展 expiration 字段。

### 4. 薄模型

模型仅提供基本的 `add()` / `remove()` 辅助方法，不包含复杂业务逻辑。

## SQL DDL

```sql
CREATE TABLE inventory (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_type    TEXT(16) NOT NULL DEFAULT 'seed'
                 CHECK(item_type IN ('seed', 'harvest', 'fertilizer', 'tool')),
    item_subtype TEXT(32) NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1 CHECK(quantity > 0),
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(user_id, item_type, item_subtype)
);

CREATE INDEX idx_inventory_user_id ON inventory(user_id);
```

## 字段说明

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `int` | PK, 自增 | 自增主键 |
| `user_id` | `int` | FK → `users.id` ON DELETE CASCADE, NOT NULL, index | 所属用户 |
| `item_type` | `str` (16) | NOT NULL, DEFAULT 'seed', CHECK enum | 物品类型：seed / harvest / fertilizer / tool |
| `item_subtype` | `str` (32) | NOT NULL | 子类型标识：wheat / carrot / ... |
| `quantity` | `int` | NOT NULL, DEFAULT 1, CHECK > 0 | 数量 |
| `created_at` | `datetime` | DEFAULT CURRENT_TIMESTAMP | 记录创建时间 |
| `updated_at` | `datetime` | DEFAULT CURRENT_TIMESTAMP | 记录更新时间 |

## 关系说明

- **User → Inventory**：一对多（一个用户持有多种物品）
- **级联删除**：用户删除时，其所有物品记录自动清除

## 模型方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `full_id` (property) | `str` | 返回 `'item_type:item_subtype'` 格式的唯一标识 |
| `add(amount)` | `None` | 增加数量（`amount > 0`，否则抛 `ValueError`） |
| `remove(amount)` | `bool` | 减少数量，数量不足返回 `False`，成功返回 `True` |

## 完整 Python 实现

```python
"""Inventory model — player's item holdings (seeds, harvests, fertilizers, tools)."""

from datetime import datetime, timezone
from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Inventory(Base):
    """背包物品表 — 合并存储同类型物品。"""
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="seed"
    )
    item_subtype: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default="CURRENT_TIMESTAMP")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        UniqueConstraint("user_id", "item_type", "item_subtype", name="uix_user_item"),
        CheckConstraint("quantity > 0", name="chk_quantity_positive"),
        CheckConstraint(
            "item_type IN ('seed', 'harvest', 'fertilizer', 'tool')",
            name="chk_item_type",
        ),
    )

    @property
    def full_id(self) -> str:
        return f"{self.item_type}:{self.item_subtype}"

    def add(self, amount: int = 1) -> None:
        if amount <= 0:
            raise ValueError("amount must be > 0")
        self.quantity += amount
        self.updated_at = datetime.now(timezone.utc)

    def remove(self, amount: int = 1) -> bool:
        if amount <= 0:
            raise ValueError("amount must be > 0")
        if self.quantity < amount:
            return False
        self.quantity -= amount
        self.updated_at = datetime.now(timezone.utc)
        return True
```

## 扩展计划

| 阶段 | 扩展内容 |
|------|----------|
| P2 | 肥料 expiration（过期自动清除） |
| P2 | 物品使用记录（audit log） |
| P3 | 合成系统（物品组合为新物品） |
