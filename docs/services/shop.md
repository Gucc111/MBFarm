# 商店服务 (ShopService)

> 商店业务逻辑：购买种子、出售作物。  
> 对应代码文件：`app/services/shop.py`

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **购买种子** | 校验种子类型 → 校验等级 → 消耗金币 → 添加种子到背包 |
| **出售作物** | 校验地块 → 校验成熟 → 收获作物 → 增加金币 |

> **注**：价格数据来自 `core/constants.py` 的 `SEEDS` 字典，不在此处硬编码。

---

## 2. 设计决策

### 异常处理

统一使用 `core/exceptions.md` 中定义的异常：

| 场景 | 异常类 | HTTP 状态码 |
|------|--------|-------------|
| 种子类型不存在 | `AppValidationError("未知的种子类型")` | 422 |
| 金币不足 | `AppValidationError("金币不足")` | 422 |
| 等级不足 | `AppValidationError("等级不足")` | 422 |
| 地块不存在 | `NotFoundError("地块不存在")` | 404 |

### 价格来源

购买价：`SEEDS[seed_type].buy_price`  
出售价：`SEEDS[seed_type].sell_price`（直接查表，无浮动系数）

### 金币操作

金币增减直接操作 `user.coins` 字段，不经过中间表。

---

## 3. 方法列表

| 方法 | 参数 | 返回值 | 异常 |
|------|------|--------|------|
| `buy_seeds(user_id, seed_type, quantity)` | — | `dict` (cost, remaining_coins) | 422 |
| `sell_crop(user_id, plot_index)` | — | `dict` (revenue, remaining_coins) | 404/422 |
| `get_shop_list(user_id)` | — | `list[ShopItem]` | — |

---

## 4. 完整 Python 实现

```python
"""Shop service — business logic for buying seeds and selling crops."""

from app.core.constants import SEEDS
from app.core.exceptions import (
    AppValidationError,
    NotFoundError,
)
from app.repositories.item_repo import ItemRepo
from app.repositories.user_repo import UserRepository
from app.models.user import User


class ShopService:
    """商店业务逻辑。"""

    def __init__(self, db):
        self.db = db
        self.item_repo = ItemRepo(db)
        self.user_repo = UserRepository(db)

    async def buy_seeds(self, user_id: int, seed_type: str, quantity: int = 1) -> dict:
        """购买种子：校验 → 扣金币 → 加种子。"""
        seed_config = SEEDS.get(seed_type)
        if seed_config is None:
            raise AppValidationError(f"未知的种子类型: {seed_type}")

        user = await self.user_repo.get_by_id(user_id)
        if user.level < seed_config.unlock_level:
            raise AppValidationError(
                f"需要等级 {seed_config.unlock_level} 才能购买 {seed_config.name}"
            )

        total_cost = seed_config.buy_price * quantity
        if user.coins < total_cost:
            raise AppValidationError(
                f"金币不足（需要 {total_cost}，当前 {user.coins}）"
            )

        # 扣金币
        user.coins -= total_cost

        # 加种子到背包
        await self.item_repo.add_item(user_id, "seed", seed_type, quantity)

        await self.db.flush()

        return {
            "seed_type": seed_type,
            "quantity": quantity,
            "total_cost": total_cost,
            "remaining_coins": user.coins,
        }

    async def sell_crop(self, user_id: int, plot_index: int) -> dict:
        """出售地块上的成熟作物。等价于 farm_service.harvest() 的金币部分。"""
        # 收获逻辑交给 FarmService，这里只负责金币结算
        raise AppValidationError("请使用 /farm/harvest 端点收获作物")

    async def get_shop_list(self, user_id: int) -> dict:
        """获取商店列表（用户可查看的种子清单）。"""
        user = await self.user_repo.get_by_id(user_id)

        seeds = []
        for seed_type, config in SEEDS.items():
            unlocked = user.level >= config.unlock_level
            seeds.append({
                "seed_type": seed_type,
                "name": config.name,
                "buy_price": config.buy_price,
                "sell_price": config.sell_price,
                "unlock_level": config.unlock_level,
                "grow_time": config.grow_time,
                "unlocked": unlocked,
            })

        return {
            "seeds": seeds,
            "user_coins": user.coins,
            "user_level": user.level,
        }
```

---

## 5. 使用方式

```python
from app.services.shop import ShopService

svc = ShopService(db)

# 购买种子
result = await svc.buy_seeds(user_id=1, seed_type="wheat", quantity=5)
# → {"seed_type": "wheat", "quantity": 5, "total_cost": 50, "remaining_coins": 450}

# 商店列表
result = await svc.get_shop_list(user_id=1)
# → {"seeds": [...], "user_coins": 450, "user_level": 1}
```

---

## 6. 与 FarmService 的关系

出售作物不在 ShopService 中实现，而是在 `FarmService.harvest()` 中直接处理：

```
用户点击"收获" → routes/farm.py → FarmService.harvest()
    ├── 校验成熟
    ├── 清除地块上的作物
    ├── user.coins += SEEDS[seed_type].sell_price
    └── user.xp += SEEDS[seed_type].xp_reward
```

这样避免了 ShopService 和 FarmService 操作同一作物导致的事务冲突。

---

## 7. 依赖关系

```
ShopService
├── ItemRepo (种子入库)
├── UserRepository (用户金币/等级)
├── core.constants.SEEDS (价格/解锁等级)
└── core.exceptions (统一异常)
```
