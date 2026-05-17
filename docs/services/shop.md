# 商店服务 (ShopService)

> 商店业务逻辑：购买种子、浏览商店列表。  
> 出售作物由 `FarmService.harvest()` 处理（收获即结算金币）。  
> 对应代码文件：`app/services/shop.py`

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **购买种子** | 校验种子类型 → 校验等级 → 消耗金币 → 添加种子到背包 |
| **商店列表** | 从 `SEED_MAP` 组装种子清单，标注解锁状态 |

> **注**：价格数据来自 `core/constants.py` 的 `SEED_MAP` 字典，不在此处硬编码。

---

## 2. 设计决策

### 异常处理

统一使用 `core/exceptions.py` 中定义的异常：

| 场景 | 异常类 | HTTP 状态码 |
|------|--------|-------------|
| 种子类型不存在 | `AppValidationError("未知的种子类型")` | 422 |
| 金币不足 | `AppValidationError("金币不足（需要 X，当前 Y）")` | 422 |
| 等级不足 | `AppValidationError("需要等级 X 才能购买 Y")` | 422 |
| 用户不存在 | `AppValidationError("用户不存在")` | 422 |

### 价格来源

购买价：`SEED_MAP[seed_type].buy_price`  
出售价：`SEED_MAP[seed_type].sell_price`（直接查表，无浮动系数）

### 金币操作

金币增减直接操作 `user.coins` 字段，不经过中间表。

### 构造函数签名

`ShopService(db, user_id)` — 构造函数接收 `user_id`（由路由层通过 `_get_service` 注入），  
而非在每个方法中传递。这遵循 `FarmService(db, user_id)` 的一致设计。

---

## 3. 方法列表

| 方法 | 参数 | 返回值 | 异常 |
|------|------|--------|------|
| `buy_seeds(seed_type, quantity)` | — | `dict` (seed_type, quantity, total_cost, remaining_coins) | 422 |
| `get_shop_list()` | — | `dict` (seeds, user_coins, user_level) | — |

> `user_id` 在构造函数中绑定，方法无需重复接收。

---

## 4. 完整 Python 实现

```python
"""Shop service — business logic for buying seeds.

Selling crops is handled via ``FarmService.harvest()`` which directly
credits coins upon harvest; no separate sell path is needed.
"""

from app.core.constants import SEED_MAP
from app.core.exceptions import AppValidationError
from app.repositories.farm_repo import FarmRepo
from app.repositories.user_repo import UserRepository


class ShopService:
    """商店业务逻辑（购买种子）。"""

    def __init__(self, db, user_id: int):
        self.db = db
        self.user_id = user_id
        self.farm_repo = FarmRepo(db)
        self.user_repo = UserRepository(db)

    # ------------------------------------------------------------------
    # 购买种子
    # ------------------------------------------------------------------

    async def buy_seeds(self, seed_type: str, quantity: int = 1) -> dict:
        """购买种子：校验种子类型 → 校验等级 → 消耗金币 → 加种子到背包。

        Args:
            seed_type: 种子类型（如 "wheat", "carrot"）
            quantity: 购买数量

        Returns:
            包含 seed_type / quantity / total_cost / remaining_coins 的字典
        """
        seed_config = SEED_MAP.get(seed_type)
        if seed_config is None:
            raise AppValidationError(f"未知的种子类型: {seed_type}")

        user = await self.user_repo.get_by_id(self.user_id)
        if user is None:
            raise AppValidationError("用户不存在")

        # 校验等级
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
        await self.farm_repo.add_item(self.user_id, "seed", seed_type, quantity)

        await self.db.flush()

        return {
            "seed_type": seed_type,
            "quantity": quantity,
            "total_cost": total_cost,
            "remaining_coins": user.coins,
        }

    # ------------------------------------------------------------------
    # 商店列表
    # ------------------------------------------------------------------

    async def get_shop_list(self) -> dict:
        """获取商店列表（用户可查看/购买的种子清单）。

        Returns:
            包含 seeds 列表 和 user_coins / user_level 的字典
        """
        user = await self.user_repo.get_by_id(self.user_id)
        if user is None:
            raise AppValidationError("用户不存在")

        seeds = []
        for seed_type, config in SEED_MAP.items():
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

svc = ShopService(db, user_id=1)

# 购买种子
result = await svc.buy_seeds("wheat", 5)
# → {"seed_type": "wheat", "quantity": 5, "total_cost": 50, "remaining_coins": 450}

# 商店列表
result = await svc.get_shop_list()
# → {"seeds": [...], "user_coins": 450, "user_level": 1}
```

---

## 6. 与 FarmService 的关系

出售作物不在 `ShopService` 中实现，而是在 `FarmService.harvest()` 中直接处理：

```
用户点击"收获" → POST /api/farm/harvest → FarmService.harvest()
    ├── 校验成熟
    ├── 清除地块上的作物
    ├── user.coins += SEED_MAP[seed_type].sell_price
    └── user.xp += SEED_MAP[seed_type].xp_reward
```

这避免了 `ShopService` 和 `FarmService` 操作同一作物导致的事务冲突。

---

## 7. 依赖关系

```
ShopService
├── FarmRepo (种子入库)
├── UserRepository (用户金币/等级)
├── core.constants.SEED_MAP (价格/解锁等级)
└── core.exceptions (统一异常)
```
