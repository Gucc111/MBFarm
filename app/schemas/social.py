"""Social module Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserBrief(BaseModel):
    """用户摘要（嵌入在好友/请求响应中）"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    level: int
    xp: int


class FriendshipResponse(BaseModel):
    """好友关系记录（含状态）"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    friend_id: int
    status: str  # pending | accepted | rejected | blocked
    created_at: datetime
    updated_at: datetime
    friend: UserBrief


class AddFriendRequest(BaseModel):
    """添加好友请求体"""
    friend_username: str = Field(
        min_length=2,
        max_length=32,
        description="对方用户名",
    )


class RespondFriendRequest(BaseModel):
    """审批好友请求"""
    friendship_id: int = Field(gt=0, description="好友关系记录 ID")
    accept: bool = Field(description="True 接受，False 拒绝")


class BlockUserRequest(BaseModel):
    """拉黑用户请求"""
    target_user_id: int = Field(gt=0, description="目标用户 ID")


class FriendListResponse(BaseModel):
    """好友列表响应"""
    friends: list[UserBrief]
    total: int
    pending_count: int = 0


class FriendStats(BaseModel):
    """好友统计"""
    pending_count: int
    friends_count: int
    max_friends: int = 50


class PendingRequestItem(BaseModel):
    """待处理请求项"""
    model_config = ConfigDict(from_attributes=True)

    friendship_id: int
    from_user_id: int
    username: str
    created_at: datetime


class PendingRequestsResponse(BaseModel):
    """待处理请求列表"""
    requests: list[PendingRequestItem]
    total: int


class ActionResponse(BaseModel):
    """通用操作响应"""
    success: bool
    message: str
    target_id: int | None = None
