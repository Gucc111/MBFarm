# Item Repository

> **注意**: Item 的 CRUD 方法已合并到 `app/repositories/farm_repo.py` 的 `FarmRepo` 类中，不再单独使用 `ItemRepo` 文件。

## 设计决策（保留供参考）

- **upsert 模式**：`add_item` 先查询再更新/插入
- **物理删除**：当 quantity ≤ 0 时物理删除记录（而非软删除）
- **数据隔离**：所有查询按 user_id 过滤

## 方法（在 FarmRepo 中）

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `get_item` | `(user_id, item_type, item_subtype)` | `Inventory \| None` | 获取指定物品 |
| `add_item` | `(user_id, item_type, item_subtype, quantity)` | `Inventory` | 添加/叠加物品（upsert） |
| `remove_item` | `(user_id, item_type, item_subtype, quantity)` | `bool` | 减少物品，归零则删除 |
| `get_user_inventory` | `(user_id)` | `list[Inventory]` | 获取全部背包物品 |

## 使用示例

```python
from app.repositories.farm_repo import FarmRepo

repo = FarmRepo(db)

# 添加种子
await repo.add_item(user_id=5, item_type="seed", item_subtype="wheat", quantity=10)

# 消耗种子
ok = await repo.remove_item(user_id=5, item_type="seed", item_subtype="wheat", quantity=1)

# 获取背包
inventory = await repo.get_user_inventory(user_id=5)
```
