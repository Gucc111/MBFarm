# Item Repository

## 模块职责

`app/repositories/item_repo.py` — 背包物品的数据访问层（CRUD + upsert 语义）。

## 设计决策

- upsert 模式：`add_item` 先查询再更新/插入
- 删除物品：当 quantity ≤ 0 时物理删除记录（而非软删除）
- 所有查询按 user_id 过滤，确保数据隔离

## Python 实现

```python
"""Item repository — data access for inventory."""

from __future__ import annotations

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Inventory


class ItemRepo:
    """背包物品的数据访问层。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Item CRUD
    # ------------------------------------------------------------------

    async def get_item(
        self,
        user_id: int,
        item_type: str,
        item_subtype: str,
    ) -> Inventory | None:
        """获取用户持有的某个物品。"""
        result = await self.db.execute(
            select(Inventory).where(
                Inventory.user_id == user_id,
                Inventory.item_type == item_type,
                Inventory.item_subtype == item_subtype,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_inventory(self, user_id: int) -> list[Inventory]:
        """获取用户的全部背包物品。"""
        result = await self.db.execute(
            select(Inventory).where(Inventory.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_items_by_type(
        self,
        user_id: int,
        item_type: str,
    ) -> list[Inventory]:
        """获取用户持有的某类物品（如全部种子）。"""
        result = await self.db.execute(
            select(Inventory).where(
                Inventory.user_id == user_id,
                Inventory.item_type == item_type,
            )
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Upsert Operations
    # ------------------------------------------------------------------

    async def add_item(
        self,
        user_id: int,
        item_type: str,
        item_subtype: str,
        quantity: int = 1,
    ) -> Inventory:
        """添加物品（upsert 语义）。"""
        if quantity <= 0:
            raise ValueError("quantity must be > 0")

        existing = await self.get_item(user_id, item_type, item_subtype)
        if existing:
            existing.add(quantity)
            await self.db.flush()
            return existing

        item = Inventory(
            user_id=user_id,
            item_type=item_type,
            item_subtype=item_subtype,
            quantity=quantity,
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def remove_item(
        self,
        user_id: int,
        item_type: str,
        item_subtype: str,
        quantity: int = 1,
    ) -> bool:
        """移除物品。如果数量不足返回 False；数量归零则删除记录。"""
        if quantity <= 0:
            raise ValueError("quantity must be > 0")

        existing = await self.get_item(user_id, item_type, item_subtype)
        if not existing:
            return False

        if existing.quantity < quantity:
            return False

        existing.remove(quantity)
        await self.db.flush()

        # 数量为 0 时删除记录
        if existing.quantity == 0:
            await self.db.delete(existing)
            await self.db.flush()

        return True

    # ------------------------------------------------------------------
    # Batch Operations
    # ------------------------------------------------------------------

    async def add_items_batch(
        self,
        user_id: int,
        items: list[tuple[str, str, int]],  # [(item_type, item_subtype, quantity), ...]
    ) -> int:
        """批量添加物品。返回成功添加的物品种类数。"""
        count = 0
        for item_type, item_subtype, quantity in items:
            if await self.add_item(user_id, item_type, item_subtype, quantity):
                count += 1
        await self.db.flush()
        return count

    async def deduct_items_batch(
        self,
        user_id: int,
        items: list[tuple[str, str, int]],
    ) -> bool:
        """批量扣减物品（全部成功才提交）。
        
        先预检所有物品是否足够，再批量执行扣减。
        """
        # 预检
        for item_type, item_subtype, quantity in items:
            existing = await self.get_item(user_id, item_type, item_subtype)
            if not existing or existing.quantity < quantity:
                return False

        # 批量扣减
        for item_type, item_subtype, quantity in items:
            await self.remove_item(user_id, item_type, item_subtype, quantity)

        return True
```

## 使用示例

```python
from app.repositories.item_repo import ItemRepo

# 购买种子（添加）
repo = ItemRepo(db)
await repo.add_item(user_id=5, item_type="seed", item_subtype="wheat", quantity=10)

# 播种（消耗种子）
ok = await repo.remove_item(user_id=5, item_type="seed", item_subtype="wheat", quantity=1)

# 获取全部背包
repo = ItemRepo(db)
inventory = await repo.get_user_inventory(user_id=5)
# → [Inventory(..., item_type="seed", item_subtype="wheat", quantity=9), ...]
```
