"""Steal module Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StealRequest(BaseModel):
    """偷菜请求体"""
    target_user_id: int = Field(gt=0, description="目标用户 ID")


class StealResult(BaseModel):
    """偷菜结果"""
    seed_type: str
    seed_name: str
    quantity: int
    value: int


class StealRecord(BaseModel):
    """偷菜记录（历史）"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    stealer_id: int | None = None
    victim_id: int | None = None
    stolen_crop_type: str
    quantity: int = 1
    stolen_at: str  # ISO format datetime


class StealHistoryResponse(BaseModel):
    """偷菜历史列表"""
    records: list[StealRecord]
    total: int
