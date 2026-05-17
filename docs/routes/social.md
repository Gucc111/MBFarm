# Social Route

## 模块职责

`app/api/routes/social.py` — 社交相关 API 端点（好友请求、好友列表、拉黑）。

## 设计决策

- 所有端点需要认证
- 操作前校验用户存在性和关系状态
- 返回友好的错误消息

## Python 实现

```python
"""Social API routes — friend requests and relationships."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.services.friend_service import FriendService, FriendServiceError

router = APIRouter(prefix="/api/social", tags=["social"])


def get_friend_service(db: AsyncSession = Depends(get_db)) -> FriendService:
    """依赖注入 FriendService。"""
    return FriendService(db)


# ------------------------------------------------------------------
# Request/Response Schemas
# ------------------------------------------------------------------

class SendRequestRequest(BaseModel):
    target_user_id: int = Field(..., description="目标用户 ID")


class AcceptRequestRequest(BaseModel):
    requester_user_id: int = Field(..., description="请求方用户 ID")


class RemoveRequest(BaseModel):
    friend_user_id: int = Field(..., description="好友用户 ID")


class FriendItem(BaseModel):
    user_id: int
    username: str
    level: int


class FriendListResponse(BaseModel):
    success: bool
    friends: list[FriendItem]


class RequestItem(BaseModel):
    requester_id: int
    username: str
    created_at: str


class PendingRequestResponse(BaseModel):
    success: bool
    requests: list[RequestItem]


class ActionResponse(BaseModel):
    success: bool
    target_id: int
    action: str


# ------------------------------------------------------------------
# Social Endpoints
# ------------------------------------------------------------------

@router.post("/friend/request", response_model=ActionResponse)
async def send_friend_request(
    body: SendRequestRequest,
    user: User = Depends(get_current_user),
    service: FriendService = Depends(get_friend_service),
):
    """发送好友请求。"""
    try:
        result = await service.send_request(user.id, body.target_user_id)
        return {
            "success": True,
            "target_id": body.target_user_id,
            "action": result["status"],
        }
    except FriendServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/friend/accept", response_model=ActionResponse)
async def accept_friend_request(
    body: AcceptRequestRequest,
    user: User = Depends(get_current_user),
    service: FriendService = Depends(get_friend_service),
):
    """接受好友请求。"""
    try:
        result = await service.accept_request(user.id, body.requester_user_id)
        return {
            "success": True,
            "target_id": body.requester_user_id,
            "action": "accepted",
        }
    except FriendServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/friend/reject", response_model=ActionResponse)
async def reject_friend_request(
    body: AcceptRequestRequest,
    user: User = Depends(get_current_user),
    service: FriendService = Depends(get_friend_service),
):
    """拒绝好友请求。"""
    try:
        result = await service.reject_request(user.id, body.requester_user_id)
        return {
            "success": True,
            "target_id": body.requester_user_id,
            "action": "rejected",
        }
    except FriendServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/friend/remove", response_model=ActionResponse)
async def remove_friend(
    body: RemoveRequest,
    user: User = Depends(get_current_user),
    service: FriendService = Depends(get_friend_service),
):
    """解除好友关系。"""
    try:
        result = await service.remove_friend(user.id, body.friend_user_id)
        return result
    except FriendServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/friend/block", response_model=ActionResponse)
async def block_user(
    body: RemoveRequest,
    user: User = Depends(get_current_user),
    service: FriendService = Depends(get_friend_service),
):
    """拉黑用户。"""
    try:
        result = await service.block_user(user.id, body.friend_user_id)
        return result
    except FriendServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/friends", response_model=FriendListResponse)
async def get_friend_list(
    user: User = Depends(get_current_user),
    service: FriendService = Depends(get_friend_service),
):
    """获取好友列表。"""
    friends = await service.get_friend_list(user.id)
    return {"success": True, "friends": friends}


@router.get("/requests/pending", response_model=PendingRequestResponse)
async def get_pending_requests(
    user: User = Depends(get_current_user),
    service: FriendService = Depends(get_friend_service),
):
    """获取待处理的好友请求。"""
    requests = await service.get_pending_requests(user.id)
    return {"success": True, "requests": requests}
```

## 路由列表

| 方法   | 路径                              | 说明             |
|--------|-----------------------------------|------------------|
| POST   | /api/social/friend/request        | 发送好友请求     |
| POST   | /api/social/friend/accept         | 接受请求         |
| POST   | /api/social/friend/reject         | 拒绝请求         |
| POST   | /api/social/friend/remove         | 解除好友         |
| POST   | /api/social/friend/block          | 拉黑用户         |
| GET    | /api/social/friends               | 好友列表         |
| GET    | /api/social/requests/pending      | 待处理请求       |

## 使用示例

```bash
# 发送好友请求
curl -X POST -H "Authorization: Bearer <token>" \
  -d '{"target_user_id": 3}' \
  http://localhost:8000/api/social/friend/request

# 获取好友列表
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/social/friends

# 获取待处理请求
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/social/requests/pending
```
