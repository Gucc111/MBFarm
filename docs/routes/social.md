# Social Route

## 模块职责

`app/routes/social.py` — 社交相关 API 端点（好友请求、好友列表、拉黑）。

路由在 `main.py` 中以 `prefix="/social"` 注册，`main.py` 统一添加 `/api` 前缀，因此最终路径为 `/api/social/...`。

## 设计决策

- 所有端点需要认证（Cookie 会话，`session_token` cookie）
- 操作前校验用户存在性和关系状态
- 返回友好的错误消息（通过全局 `AppError` 异常处理器，非 `HTTPException`）
- 审批好友请求使用单一 `/friend/respond` 端点，通过 `accept` 字段区分接受/拒绝
- 按用户名添加好友，无需传用户 ID

## Python 实现

```python
"""Social API routes — friend requests and relationships."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.social import (
    ActionResponse,
    AddFriendRequest,
    BlockUserRequest,
    FriendListResponse,
    PendingRequestsResponse,
    RespondFriendRequest,
    UserBrief,
)
from app.services.friend import FriendService

router = APIRouter(prefix="/social", tags=["社交"])


def _get_service(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FriendService:
    return FriendService(db)


@router.post(
    "/friend/request",
    response_model=ActionResponse,
    status_code=status.HTTP_200_OK,
    summary="发送好友请求",
)
async def send_friend_request(
    body: AddFriendRequest,
    svc: FriendService = Depends(_get_service),
    user: User = Depends(get_current_user),
):
    result = await svc.add_friend(user.id, body.friend_username)
    return ActionResponse(success=True, message="好友请求已发送", target_id=result["friendship_id"])


@router.post(
    "/friend/respond",
    response_model=ActionResponse,
    status_code=status.HTTP_200_OK,
    summary="审批好友请求",
)
async def respond_friend_request(
    body: RespondFriendRequest,
    svc: FriendService = Depends(_get_service),
    user: User = Depends(get_current_user),
):
    result = await svc.respond_to_request(user.id, body.friendship_id, body.accept)
    action = "接受了好友请求" if body.accept else "拒绝了好友请求"
    return ActionResponse(success=True, message=action, target_id=result["friendship_id"])


@router.get(
    "/friends",
    response_model=FriendListResponse,
    summary="获取好友列表",
)
async def get_friend_list(
    svc: FriendService = Depends(_get_service),
    user: User = Depends(get_current_user),
):
    result = await svc.get_friend_list(user.id)
    return FriendListResponse(
        friends=[UserBrief(**f) for f in result["friends"]],
        total=result["total"],
        pending_count=result["pending_count"],
    )


@router.get(
    "/requests/pending",
    response_model=PendingRequestsResponse,
    summary="获取待处理好友请求",
)
async def get_pending_requests(
    svc: FriendService = Depends(_get_service),
    user: User = Depends(get_current_user),
):
    result = await svc.get_pending_requests(user.id)
    return PendingRequestsResponse(requests=result["requests"], total=result["total"])


@router.post(
    "/friend/block",
    response_model=ActionResponse,
    status_code=status.HTTP_200_OK,
    summary="拉黑用户",
)
async def block_user(
    body: BlockUserRequest,
    svc: FriendService = Depends(_get_service),
    user: User = Depends(get_current_user),
):
    result = await svc.block_user(user.id, body.target_user_id)
    return ActionResponse(success=True, message="已拉黑用户", target_id=result["target_id"])


@router.post(
    "/friend/remove",
    response_model=ActionResponse,
    status_code=status.HTTP_200_OK,
    summary="解除好友关系",
)
async def remove_friend(
    body: BlockUserRequest,
    svc: FriendService = Depends(_get_service),
    user: User = Depends(get_current_user),
):
    result = await svc.remove_friend(user.id, body.target_user_id)
    return ActionResponse(success=True, message="已解除好友关系", target_id=result["friend_id"])
```

## 路由列表

| 方法   | 路径                              | 说明             |
|--------|-----------------------------------|------------------|
| POST   | /api/social/friend/request        | 发送好友请求     |
| POST   | /api/social/friend/respond        | 审批好友请求     |
| GET    | /api/social/friends               | 好友列表         |
| GET    | /api/social/requests/pending      | 待处理请求       |
| POST   | /api/social/friend/block          | 拉黑用户         |
| POST   | /api/social/friend/remove         | 解除好友         |

## 请求/响应示例

### 发送好友请求

```bash
curl -X POST -b "session_token=xxx" \
  -H "Content-Type: application/json" \
  -d '{"friend_username": "alice"}' \
  http://localhost:8000/api/social/friend/request
```

响应:
```json
{"success": true, "message": "好友请求已发送", "target_id": 5}
```

### 审批好友请求

```bash
curl -X POST -b "session_token=xxx" \
  -H "Content-Type: application/json" \
  -d '{"friendship_id": 5, "accept": true}' \
  http://localhost:8000/api/social/friend/respond
```

### 获取好友列表

```bash
curl -b "session_token=xxx" \
  http://localhost:8000/api/social/friends
```

响应:
```json
{
  "friends": [
    {"id": 1, "username": "alice", "level": 2, "xp": 120}
  ],
  "total": 1,
  "pending_count": 0
}
```

### 拉黑用户

```bash
curl -X POST -b "session_token=xxx" \
  -H "Content-Type: application/json" \
  -d '{"target_user_id": 3}' \
  http://localhost:8000/api/social/friend/block
```
