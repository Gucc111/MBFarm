"""Pydantic v2 schemas for user authentication endpoints."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ── Request Schemas ──────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """用户注册请求体"""
    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    """用户登录请求体"""
    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)


# ── Response Schemas ─────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    """用户信息响应（不含密码）"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    coins: int
    xp: int
    level: int
    created_at: datetime


class LoginResponse(BaseModel):
    """登录成功响应"""
    user: UserResponse
    message: str
