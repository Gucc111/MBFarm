# 好友服务 (FriendService)

> 好友关系业务逻辑：发送/接受/拒绝好友请求、好友列表、拉黑、解除好友。  
> 对应代码文件：`app/services/friend.py`

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **发送好友请求** | 按用户名查找目标 → 校验 → 调用 `SocialRepo.send_request`（通知系统 TODO） |
| **接受/拒绝请求** | 调用 `SocialRepo.accept_request` / `reject_request`（repo 层创建双向关系） |
| **好友列表** | 查询所有 accepted 关系，返回好友信息 + 待处理计数 |
| **拉黑用户** | 调用 `SocialRepo.block_user`，无需已有关系 |
| **解除好友** | 调用 `SocialRepo.remove_friendship` 删除双向记录 |

---

## 2. 设计决策

### 异常处理

统一使用 `app/core/exceptions.py` 中定义的 `AppError` 子类，由 `main.py` 的全局异常处理器转换为 JSON 响应：

| 业务场景 | 异常类 | HTTP 状态码 |
|----------|--------|-------------|
| 添加自己为好友 | `AppValidationError("不能添加自己为好友")` | 422 |
| 已被对方拉黑 | `ForbiddenError("你已被对方拉黑")` | 403 |
| 请求不存在 | `NotFoundError("好友请求不存在")` | 404 |
| 重复请求 | `ConflictError("已发送过好友请求")` | 409 |
| 好友已满 | `ConflictError("好友已达上限")` | 409 |
| 用户不存在 | `NotFoundError("用户不存在: {username}")` | 404 |

### 按用户名添加好友

`add_friend` 接收 `friend_username`（字符串），通过 `UserRepository.get_by_username` 查找目标用户。这样前端无需维护用户 ID 映射。

### 好友上限

每人最多 `SYSTEM.max_friends`（50）位好友，在 service 层通过 `SocialRepo.count_friends` 校验。

### 通知（TODO）

通知系统尚未实现。`add_friend` 中有 TODO 注释，待 `NotificationService` 上线后补充。

---

## 3. 方法列表

| 方法 | 参数 | 返回值 | 异常 |
|------|------|--------|------|
| `add_friend(user_id, friend_username)` | — | `dict` (friendship_id, status) | 422/403/409 |
| `respond_to_request(user_id, friendship_id, accept)` | — | `dict` (friendship_id, status) | 404/422 |
| `get_friend_list(user_id)` | — | `dict` (friends, total, pending_count) | — |
| `get_pending_requests(user_id)` | — | `dict` (requests, total) | — |
| `block_user(user_id, target_id)` | — | `dict` (target_id, action) | 422 |
| `remove_friend(user_id, friend_id)` | — | `dict` (friend_id, action) | — |

---

## 4. 完整 Python 实现

```python
"""Friend service — business logic for friend management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SYSTEM
from app.core.exceptions import (
    AppValidationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.repositories.social_repo import SocialRepo
from app.repositories.user_repo import UserRepository


class FriendService:
    """好友关系业务逻辑。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.social_repo = SocialRepo(db)
        self.user_repo = UserRepository(db)

    async def add_friend(self, user_id: int, friend_username: str) -> dict:
        """发送好友请求。"""
        target = await self.user_repo.get_by_username(friend_username)
        if target is None:
            raise NotFoundError(f"用户不存在: {friend_username}")
        if target.id == user_id:
            raise AppValidationError("不能添加自己为好友")

        block = await self.social_repo.get_friendship(target.id, user_id)
        if block and block.status == "blocked":
            raise ForbiddenError("你已被对方拉黑")

        existing = await self.social_repo.get_friendship(user_id, target.id)
        if existing:
            if existing.status == "accepted":
                raise ConflictError("已是好友")
            if existing.status == "pending":
                raise ConflictError("已发送过好友请求，等待对方回应")

        friend_count = await self.social_repo.count_friends(user_id)
        if friend_count >= SYSTEM.max_friends:
            raise ConflictError(f"好友已达上限 ({SYSTEM.max_friends})")

        friendship = await self.social_repo.send_request(user_id, target.id)
        # TODO: 通知系统上线后添加

        return {"friendship_id": friendship.id, "status": "pending"}

    async def respond_to_request(self, user_id: int, friendship_id: int, accept: bool) -> dict:
        """审批好友请求。"""
        friendship = await self.social_repo.get_by_id(friendship_id)
        if friendship is None or friendship.friend_id != user_id:
            raise NotFoundError("好友请求不存在")
        if friendship.status != "pending":
            raise AppValidationError("请求已处理")

        if accept:
            await self.social_repo.accept_request(friendship.user_id, user_id)
            new_status = "accepted"
        else:
            await self.social_repo.reject_request(friendship.user_id, user_id)
            new_status = "rejected"

        return {"friendship_id": friendship_id, "status": new_status}

    async def get_friend_list(self, user_id: int) -> dict:
        """获取好友列表。"""
        friendships = await self.social_repo.get_friends(user_id)
        friends = []
        for f in friendships:
            if f.friend:
                friends.append({
                    "id": f.friend.id,
                    "username": f.friend.username,
                    "level": f.friend.level,
                    "xp": f.friend.xp,
                })
        pending_count = await self.social_repo.count_pending_received(user_id)
        return {
            "friends": friends,
            "total": len(friends),
            "pending_count": pending_count,
        }

    async def get_pending_requests(self, user_id: int) -> dict:
        """获取待处理的请求。"""
        pending = await self.social_repo.get_pending_received(user_id)
        requests = []
        for p in pending:
            if p.user:
                requests.append({
                    "friendship_id": p.id,
                    "from_user_id": p.user.id,
                    "username": p.user.username,
                    "created_at": p.created_at.isoformat(),
                })
        return {"requests": requests, "total": len(requests)}

    async def block_user(self, user_id: int, target_id: int) -> dict:
        """拉黑用户。"""
        if user_id == target_id:
            raise AppValidationError("不能拉黑自己")
        await self.social_repo.block_user(user_id, target_id)
        return {"target_id": target_id, "action": "blocked"}

    async def remove_friend(self, user_id: int, friend_id: int) -> dict:
        """解除好友（删除双向记录）。"""
        await self.social_repo.remove_friendship(user_id, friend_id)
        return {"friend_id": friend_id, "action": "removed"}
```

---

## 5. 依赖关系

```
FriendService
├── SocialRepo (好友 CRUD)
├── UserRepository (用户名查询)
├── core.constants.SYSTEM.max_friends
├── core.exceptions (统一异常)
└── NotificationService (TODO，尚未实现)
```
