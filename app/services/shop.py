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

        await self.db.commit()

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
