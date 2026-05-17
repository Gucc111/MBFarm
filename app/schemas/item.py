"""Pydantic schemas for inventory endpoints."""

from pydantic import BaseModel, ConfigDict


# ── Response Schemas ─────────────────────────────────────────────────────────

class InventoryItem(BaseModel):
    """背包物品"""
    model_config = ConfigDict(from_attributes=True)

    item_type: str
    item_subtype: str
    quantity: int


class InventoryResponse(BaseModel):
    """背包响应"""
    items: list[InventoryItem]
    total_coins: int
