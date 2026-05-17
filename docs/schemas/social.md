# 社交模块 Pydantic Schema

> 定义社交模块（好友系统）的 Pydantic v2 数据验证模型。  
> 对应代码文件：`app/schemas/social.py`

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **请求校验** | 校验好友添加、审批请求的输入参数 |
| **响应序列化** | 定义好友列表、好友请求、好友信息的响应格式 |
| **嵌套用户摘要** | 提供 `UserBrief` 嵌入好友相关响应 |

> **注**：通知相关的 Schema 定义在 `schemas/notification.md`，不属于本模块。

---

## 2. Schema 列表

| 类名 | 用途 | 类型 | 字段数 |
|------|------|------|--------|
| `UserBrief` | 用户摘要（嵌入用） | 响应 | 5 |
| `FriendshipResponse` | 好友关系记录 | 响应 | 7 |
| `AddFriendRequest` | 添加好友请求体 | 请求 | 1 |
| `RespondFriendRequest` | 审批好友请求体 | 请求 | 2 |
| `FriendInfoResponse` | 单个好友信息 | 响应 | 6 |
| `FriendListResponse` | 好友列表响应 | 响应 | 3 |
| `FriendStats` | 好友统计 | 响应 | 3 |

---

## 3. 字段校验规则

| Schema | 字段 | 规则 |
|--------|------|------|
| `AddFriendRequest` | `friend_username` | `str`, `min_length=2`, `max_length=32` |
| `RespondFriendRequest` | `friendship_id` | `int`, 必须 > 0 |
| `RespondFriendRequest` | `accept` | `bool` |

---

## 4. 完整 Python 实现

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserBrief(BaseModel):
    """用户摘要（嵌入在好友/请求响应中）"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    level: int
    xp: int
    avatar: Optional[str] = None


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


class FriendInfoResponse(BaseModel):
    """好友详细信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    friend_id: int
    friend: UserBrief
    status: str
    created_at: datetime


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
```

---

## 5. 与 routes/social.md 集成

```python
from fastapi import APIRouter, Depends
from app.schemas.social import (
    AddFriendRequest, RespondFriendRequest,
    FriendListResponse, FriendStats,
)

router = APIRouter(prefix="/friends", tags=["friends"])


@router.post("/request", status_code=201)
async def send_friend_request(
    payload: AddFriendRequest,
    user: User = Depends(get_current_user),
    svc: FriendService = Depends(get_friend_service),
):
    """发送好友请求"""
    ...


@router.post("/respond")
async def respond_to_request(
    payload: RespondFriendRequest,
    user: User = Depends(get_current_user),
    svc: FriendService = Depends(get_friend_service),
):
    """审批好友请求"""
    ...


@router.get("/", response_model=FriendListResponse)
async def get_friend_list(
    user: User = Depends(get_current_user),
    svc: FriendService = Depends(get_friend_service),
):
    """获取好友列表"""
    ...


@router.get("/stats", response_model=FriendStats)
async def get_friend_stats(
    user: User = Depends(get_current_user),
    svc: FriendService = Depends(get_friend_service),
):
    """获取好友统计"""
    ...
```

---

## 6. 设计决策

### 为什么不在 Schema 中区分 FriendRequest 和 Friendship？

social.md 模型采用**单表设计**（一张 `friendships` 表，用 `status` 字段区分 pending/accepted/rejected/blocked），因此 Schema 也统一用 `FriendshipResponse` 表示，通过 `status` 字段区分请求和已确认好友。

### UserBrief 的复用

`UserBrief` 在好友列表、好友请求、成就解锁等多个模块中复用。当用户模型新增字段时，只需在 `UserBrief` 中添加即可。
