"""Farm service — business logic for planting, harvesting, watering, and plot management."""

from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.constants import FARM, INIT_USER, SEEDS, SEED_MAP, STAMINA
from app.core.exceptions import AppValidationError, ConflictError, NotFoundError
from app.repositories.farm_repo import FarmRepo
from app.repositories.user_repo import UserRepository
from app.schemas.farm import (
    CropInfo,
    FarmInfoResponse,
    PlotResponse,
    UserFarmInfo,
)
from app.services.game_engine import calc_level_from_xp, calc_growth_stage, get_mature_at, is_mature, restore_stamina
from app.models.farm import Crop, Plot

# Mapping from seed_type (item_subtype) → SeedConfig
# SEED_MAP already keyed by id (e.g. "wheat")

__all__ = ["FarmService", "farm_service_dep"]


class FarmService:
    """农场核心业务逻辑。"""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id
        self.farm_repo = FarmRepo(db)
        self.user_repo = UserRepository(db)

    # ------------------------------------------------------------------
    # 体力管理
    # ------------------------------------------------------------------

    async def _ensure_stamina(self, cost: int) -> None:
        """恢复离线体力并校验是否足够，不足则抛异常。"""
        user = await self.user_repo.get_by_id(self.user_id)
        if user is None:
            raise NotFoundError("用户不存在")

        # 恢复离线体力
        if user.last_active_at is not None:
            user.stamina = restore_stamina(
                current_stamina=user.stamina,
                last_active=user.last_active_at,
                max_stamina=STAMINA.max_value,
                restore_per_minute=STAMINA.regen_per_min,
            )

        if user.stamina < cost:
            raise AppValidationError(
                f"体力不足（需要 {cost}，当前 {user.stamina}）"
            )

        user.stamina -= cost
        user.last_active_at = datetime.now(timezone.utc)

    async def _persist_user(self, user) -> None:
        """将用户变更刷入数据库。"""
        user.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _seed_for(self, seed_type: str) -> object | None:
        """查找种子配置。"""
        return SEED_MAP.get(seed_type)

    async def _is_crop_mature(self, crop: Crop) -> bool:
        """判断作物是否成熟（从 crop 对象直接计算）。"""
        seed = self._seed_for(crop.seed_type)
        if not seed:
            return False
        return is_mature(crop.plant_time, crop.duration, crop.watered_times, seed.water_bonus)

    def _make_crop_info(self, crop: Crop) -> CropInfo | None:
        """从 Crop ORM 构建 CropInfo Pydantic 对象。"""
        seed = self._seed_for(crop.seed_type)
        if not seed:
            return None
        water_bonus = seed.water_bonus
        return CropInfo(
            seed_type=crop.seed_type,
            seed_name=seed.name,
            plant_time=crop.plant_time,
            watered_times=crop.watered_times,
            is_mature=is_mature(crop.plant_time, crop.duration, crop.watered_times, water_bonus),
            mature_at=get_mature_at(crop.plant_time, crop.duration, crop.watered_times, water_bonus),
            growth_stage=calc_growth_stage(crop.plant_time, crop.duration, crop.watered_times, water_bonus),
        )

    def _make_plot_response(self, plot: Plot) -> PlotResponse:
        """从 Plot ORM 构建 PlotResponse。"""
        return PlotResponse(
            index=plot.index,
            level=plot.level,
            crop=self._make_crop_info(plot.current_crop) if plot.current_crop else None,
            watered_times=plot.watered_times,
            planted_at=plot.planted_at,
        )

    # ------------------------------------------------------------------
    # 种植
    # ------------------------------------------------------------------

    async def plant(self, plot_index: int, seed_type: str) -> Crop:
        """播种：校验等级 → 消耗种子 → 消耗体力 → 创建作物。

        Args:
            plot_index: 地块编号 (1-based)
            seed_type: 种子类型 (如 "wheat", "carrot")

        Returns:
            创建成功的 Crop 对象
        """
        seed_config = SEED_MAP.get(seed_type)
        if seed_config is None:
            raise AppValidationError(f"未知的种子类型: {seed_type}")

        # 校验等级
        user = await self.user_repo.get_by_id(self.user_id)
        if user.level < seed_config.unlock_level:
            raise AppValidationError(
                f"需要等级 {seed_config.unlock_level} 才能种植 {seed_config.name}"
            )

        # 校验地块
        plot = await self.farm_repo.get_plot_by_index(self.user_id, plot_index)
        if plot is None:
            raise NotFoundError("地块不存在")
        if plot.crop_id is not None:
            raise ConflictError("地块已有作物")

        # 消耗种子
        ok = await self.farm_repo.remove_item(self.user_id, "seed", seed_type, quantity=1)
        if not ok:
            raise AppValidationError(f"种子不足: {seed_config.name}")

        # 消耗体力
        await self._ensure_stamina(STAMINA.plant_cost)

        # 种植
        return await self.farm_repo.plant_crop(
            plot_id=plot.id,
            user_id=self.user_id,
            seed_type=seed_type,
            duration=seed_config.grow_time,
        )

    # ------------------------------------------------------------------
    # 收获
    # ------------------------------------------------------------------

    async def harvest(self, plot_index: int) -> dict:
        """收获：校验成熟 → 标记收获 → 增加 XP/金币 → 检查升级。

        Args:
            plot_index: 地块编号 (1-based)

        Returns:
            收获结果字典
        """
        plot = await self.farm_repo.get_plot_by_index(self.user_id, plot_index)
        if plot is None:
            raise NotFoundError("地块不存在")

        crop = await self.farm_repo.get_crop(plot.crop_id)
        if crop is None:
            raise NotFoundError("地块没有作物")

        seed_config = SEED_MAP.get(crop.seed_type)
        if seed_config is None:
            raise NotFoundError(f"未知的种子类型: {crop.seed_type}")

        if not is_mature(crop.plant_time, crop.duration, crop.watered_times, seed_config.water_bonus):
            raise AppValidationError("作物尚未成熟")

        # 收获：清除地块上的作物
        await self.farm_repo.harvest_crop(plot)

        # 增加 XP 和金币
        user = await self.user_repo.get_by_id(self.user_id)
        xp_before = user.xp
        user.xp += seed_config.xp_reward
        user.coins += seed_config.sell_price

        # 检查升级
        new_level = calc_level_from_xp(user.xp)
        if new_level > user.level:
            user.level = new_level

        user.last_active_at = datetime.now(timezone.utc)
        await self._persist_user(user)

        return {
            "seed_type": crop.seed_type,
            "seed_name": seed_config.name,
            "xp_reward": seed_config.xp_reward,
            "coins_earned": seed_config.sell_price,
            "new_level": new_level,
            "xp_before": xp_before,
            "xp_after": user.xp,
        }

    # ------------------------------------------------------------------
    # 浇水
    # ------------------------------------------------------------------

    async def water(self, plot_index: int) -> dict:
        """浇水：校验地块 → 消耗体力 → 增加浇水次数。

        Args:
            plot_index: 地块编号 (1-based)

        Returns:
            浇水结果字典
        """
        plot = await self.farm_repo.get_plot_by_index(self.user_id, plot_index)
        if plot is None:
            raise NotFoundError("地块不存在")
        if plot.crop_id is None:
            raise NotFoundError("地块没有作物")

        crop = await self.farm_repo.get_crop(plot.crop_id)
        seed_config = SEED_MAP.get(crop.seed_type)
        if not seed_config:
            raise NotFoundError(f"未知的种子类型: {crop.seed_type}")

        if is_mature(crop.plant_time, crop.duration, crop.watered_times, seed_config.water_bonus):
            raise AppValidationError("作物已经成熟，无需浇水")

        # 消耗体力
        await self._ensure_stamina(STAMINA.water_cost)

        # 浇水
        cropped = await self.farm_repo.water_crop(plot)

        # 计算成熟时间和阶段
        mature_at = None
        if cropped:
            mature_at = get_mature_at(
                cropped.plant_time, cropped.duration, cropped.watered_times, seed_config.water_bonus
            )

        return {
            "plot_index": plot_index,
            "watered_times": plot.watered_times,
            "mature_at": mature_at.isoformat() if mature_at else None,
            "growth_stage": calc_growth_stage(
                cropped.plant_time,
                cropped.duration,
                cropped.watered_times,
                seed_config.water_bonus,
            ) if cropped else "",
        }

    # ------------------------------------------------------------------
    # 解锁地块
    # ------------------------------------------------------------------

    async def unlock_plot(self) -> dict:
        """解锁新地块。

        Returns:
            解锁结果字典
        """
        user = await self.user_repo.get_by_id(self.user_id)

        unlocked_count = await self.farm_repo.count_unlocked_plots(self.user_id)
        if unlocked_count >= FARM.max_plots:
            raise AppValidationError("已达到最大地块数")

        cost = FARM.plot_upgrade_cost
        if user.coins < cost:
            raise AppValidationError(f"金币不足（需要 {cost}，当前 {user.coins}）")

        user.coins -= cost
        new_index = unlocked_count + 1
        new_plot = await self.farm_repo.create_plot(self.user_id, new_index)
        user.last_active_at = datetime.now(timezone.utc)
        await self._persist_user(user)

        return {
            "plot_index": new_plot.index,
            "remaining_coins": user.coins,
            "total_plots": unlocked_count + 1,
        }

    # ------------------------------------------------------------------
    # 农场信息
    # ------------------------------------------------------------------

    async def get_farm_info(self) -> dict:
        """获取农场完整信息（内部数据用）。"""
        user = await self.user_repo.get_by_id(self.user_id)

        # 恢复离线体力
        if user.last_active_at is not None:
            user.stamina = restore_stamina(
                current_stamina=user.stamina,
                last_active=user.last_active_at,
                max_stamina=STAMINA.max_value,
                restore_per_minute=STAMINA.regen_per_min,
            )

        plots = await self.farm_repo.get_user_plots(self.user_id)

        return {
            "user_id": self.user_id,
            "plots": plots,
            "stamina": user.stamina,
            "coins": user.coins,
            "level": user.level,
            "xp": user.xp,
        }

    async def get_farm_info_response(self) -> FarmInfoResponse:
        """获取农场完整信息，返回 Pydantic response_model 兼容的对象。"""
        info = await self.get_farm_info()
        plots_resp = [self._make_plot_response(p) for p in info["plots"]]
        user_resp = UserFarmInfo(
            id=info["user_id"],
            username="",
            coins=info["coins"],
            stamina=info["stamina"],
            xp=info["xp"],
            level=info["level"],
        )
        return FarmInfoResponse(
            user=user_resp,
            plots=plots_resp,
            max_plots=FARM.max_plots,
        )


def farm_service_dep(
    db: AsyncSession = Depends(get_db),
    user: "User" = Depends(get_current_user),  # type: ignore[name-defined]
) -> FarmService:
    """FastAPI 依赖注入：返回绑定当前用户的 FarmService。"""
    return FarmService(db, user.id)
