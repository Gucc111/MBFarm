"""Pydantic schemas for farm endpoints (plant, harvest, water, unlock, status)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Request Schemas ──────────────────────────────────────────────────────────

class PlantRequest(BaseModel):
    """种植请求体"""
    plot_index: int = Field(..., ge=1, le=25, description="地块编号 (1-based)")
    seed_type: str = Field(..., min_length=1, max_length=32, description="种子类型 (如 wheat, carrot)")


class WaterRequest(BaseModel):
    """浇水请求体"""
    plot_index: int = Field(..., ge=1, le=25, description="地块编号 (1-based)")


class HarvestRequest(BaseModel):
    """收获请求体"""
    plot_index: int = Field(..., ge=1, le=25, description="地块编号 (1-based)")


# ── Response Schemas ─────────────────────────────────────────────────────────

class SeedInfo(BaseModel):
    """种子信息"""
    id: str
    name: str
    buy_price: int
    sell_price: int
    grow_time: int
    xp_reward: int
    unlock_level: int
    water_bonus: int


class CropInfo(BaseModel):
    """地块上的作物信息"""
    seed_type: str
    seed_name: str
    plant_time: datetime
    watered_times: int
    is_mature: bool
    mature_at: datetime | None = None
    growth_stage: str  # "seedling" | "growing" | "almost_mature" | "mature"


class PlotResponse(BaseModel):
    """单个地块响应"""
    model_config = ConfigDict(from_attributes=True)

    index: int
    level: int
    crop: CropInfo | None = None
    watered_times: int
    planted_at: datetime | None = None


class UserFarmInfo(BaseModel):
    """农场用户信息（合并用户 + 农场状态）"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    coins: int
    stamina: int
    xp: int
    level: int


class FarmInfoResponse(BaseModel):
    """农场完整信息响应"""
    user: UserFarmInfo
    plots: list[PlotResponse]
    max_plots: int = Field(ge=1, description="最大可解锁地块数")


class HarvestResult(BaseModel):
    """收获结果"""
    seed_type: str
    seed_name: str
    xp_reward: int
    coins_earned: int
    new_level: int
    xp_before: int
    xp_after: int


class UnlockResult(BaseModel):
    """解锁地块结果"""
    plot_index: int
    remaining_coins: int
    total_plots: int


class WaterResult(BaseModel):
    """浇水结果"""
    plot_index: int
    watered_times: int
    mature_at: datetime | None = None
    growth_stage: str
