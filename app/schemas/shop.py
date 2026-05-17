"""Pydantic schemas for shop endpoints (buy seeds, shop list)."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import SEEDS, SEED_MAP


# ── Request Schemas ──────────────────────────────────────────────────────────

class BuySeedRequest(BaseModel):
    """购买种子请求体"""
    seed_type: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="种子类型（如 wheat, carrot）",
    )
    quantity: int = Field(
        ...,
        ge=1,
        le=99,
        description="购买数量",
    )

    @field_validator("seed_type")
    @classmethod
    def check_seed_type(cls, v: str) -> str:
        if v not in SEED_MAP:
            raise ValueError(f"未知的种子类型: {v}")
        return v


# ── Response Schemas ─────────────────────────────────────────────────────────

class BuySeedResponse(BaseModel):
    """购买结果"""
    seed_type: str
    quantity: int
    total_cost: int
    remaining_coins: int


class ShopItem(BaseModel):
    """商店商品条目"""
    model_config = ConfigDict(from_attributes=True)

    seed_type: str
    name: str
    buy_price: int
    sell_price: int
    unlock_level: int
    grow_time: int  # 秒


class ShopListResponse(BaseModel):
    """商店列表"""
    seeds: list[ShopItem]
    user_coins: int
