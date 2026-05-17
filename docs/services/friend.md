# 好友服务 (FriendService)

> 好友关系业务逻辑：发送/接受/拒绝好友请求、好友列表、拉黑、解除好友。  
> 对应代码文件：`app/services/friend.py`

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **发送好友请求** | 校验 → 创建 pending 记录 → 创建通知 |
| **接受/拒绝请求** | 更新 status → 接受时创建双向关系 → 创建通知 |
| **好友列表** | 查询所有 accepted 关系 |
| **拉黑用户** | 设置 status=blocked → 阻止对方操作 |
| **解除好友** | 删除双向 friendship 记录 |

---

## 2. 设计决策

### 异常处理

统一使用 `core/exceptions.md` 中定义的 `AppError` 子类：

| 业务场景 | 异常类 | HTTP 状态码 |
|----------|--------|-------------|
| 添加自己为好友 | `AppValidationError("不能添加自己为好友")` | 422 |
| 已被对方拉黑 | `ForbiddenError("你已被对方拉黑")` | 403 |
| 请求不存在 | `NotFoundError("好友请求不存在")` | 404 |
| 重复请求 | `ConflictError("已发送过好友请求")` | 409 |
| 好友已满 | `ConflictError("好友已达上限")` | 409 |

### 单表设计

好友关系使用单表 `friendships`（定义在 `models/social.md`），通过 `status` 字段区分：
- `pending` = 请求待处理
- `accepted` = 已确认好友
- `rejected` = 已拒绝
- `blocked` = 已拉黑

接受好友请求时创建**两条记录**（A→B 和 B→A 均为 accepted），确保查询任一方向都能找到好友。

### 好友上限

每人最多 50 位好友（`core/constants.py` 的 `MAX_FRIENDS`），在 service 层校验。

---

## 3. 方法列表

| 方法 | 参数 | 返回值 | 异常 |
|------|------|--------|------|
| `add_friend(user_id, friend_username)` | — | `Friendship` | 422/403/409 |
| `respond_to_request(user_id, friendship_id, accept)` | — | `dict` | 404/422 |
| `get_friend_list(user_id)` | — | `list[FriendResponse]` | — |
| `get_pending_requests(user_id)` | — | `list[dict]` | — |
| `block_user(user_id, target_id)` | — | `dict` | 404 |
| `remove_friend(user_id, friend_id)` | — | `dict` | 404 |

---

## 4. 完整 Python 实现

```python
"""Friend service — business logic for friend management."""

from app.core.constants import MAX_FRIENDS
from app.core.exceptions import (
    AppValidationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.repositories.social_repo import SocialRepo
from app.repositories.user_repo import UserRepository
from app.services.notification import NotificationService


class FriendService:
    """好友关系业务逻辑。"""

    def __init__(self, db):
        self.db = db
        self.social_repo = SocialRepo(db)
        self.user_repo = UserRepository(db)
        self.notif_service = NotificationService(db)

    async def add_friend(self, user_id: int, friend_username: str) -> dict:
        """发送好友请求。"""
        target = await self.user_repo.get_by_username(friend_username)
        if target is None:
            raise NotFoundError(f"用户不存在: {friend_username}")
        if target.id == user_id:
            raise AppValidationError("不能添加自己为好友")

        # 检查是否被拉黑
        block = await self.social_repo.get_friendship(target.id, user_id)
        if block and block.status == "blocked":
            raise ForbiddenError("你已被对方拉黑")

        # 检查是否已有请求或已是好友
        existing = await self.social_repo.get_friendship(user_id, target.id)
        if existing:
            if existing.status == "accepted":
                raise ConflictError("已是好友")
            if existing.status == "pending":
                raise ConflictError("已发送过好友请求，等待对方回应")

        # 检查好友上限
        friend_count = await self.social_repo.count_friends(user_id)
        if friend_count >= MAX_FRIENDS:
            raise ConflictError(f"好友已达上限 ({MAX_FRIENDS})")

        friendship = await self.social_repo.create_friendship(
            user_id=user_id,
            friend_id=target.id,
            status="pending",
        )

        # 创建通知
        await self.notif_service.create(
            user_id=target.id,
            type="friend_request",
            title="收到好友请求",
            message=f"{friend_username} 请求添加你为好友",
            from_user_id=user_id,
        )

        return {"friendship_id": friendship.id, "status": "pending"}

    async def respond_to_request(self, user_id: int, friendship_id: int, accept: bool) -> dict:
        """审批好友请求。"""
        friendship = await self.social_repo.get_by_id(friendship_id)
        if friendship is None or friendship.friend_id != user_id:
            raise NotFoundError("好友请求不存在")
        if friendship.status != "pending":
            raise AppValidationError("请求已处理")

        if accept:
            # 更新原始请求为 accepted
            await self.social_repo.update_status(friendship_id, "accepted")
            # 创建反向关系
            await self.social_repo.create_friendship(
                user_id=friendship.user_id,
                friend_id=user_id,
                status="accepted",
            )
            new_status = "accepted"
        else:
            await self.social_repo.update_status(friendship_id, "rejected")
            new_status = "rejected"

        return {"friendship_id": friendship_id, "status": new_status}

    async def get_friend_list(self, user_id: int) -> list[dict]:
        """获取好友列表。"""
        friendships = await self.social_repo.get_friends(user_id)
        return [
            {
                "id": f.id,
                "friend_id": f.friend_id,
                "status": f.status,
                "created_at": f.created_at.isoformat(),
            }
            for f in friendships
        ]

    async def get_pending_requests(self, user_id: int) -> list[dict]:
        """获取待处理的请求。"""
        pending = await self.social_repo.get_pending_received(user_id)
        return [
            {
                "friendship_id": p.id,
                "from_user_id": p.user_id,
                "created_at": p.created_at.isoformat(),
            }
            for p in pending
        ]

    async def block_user(self, user_id: int, target_id: int) -> dict:
        """拉黑用户。"""
        friendship = await self.social_repo.get_friendship(user_id, target_id)
        if friendship is None:
            raise NotFoundError("与该用户无好友关系")

        await self.social_repo.update_status(friendship.id, "blocked")
        return {"target_id": target_id, "action": "blocked"}

    async def remove_friend(self, user_id: int, friend_id: int) -> dict:
        """解除好友（删除双向记录）。"""
        await self.social_repo.remove_friendship(user_id, friend_id)
        return {"friend_id": friend_id, "action": "removed"}
```

---

## 5. 使用方式

```python
from app.services.friend import FriendService

svc = FriendService(db)

# 发送好友请求
await svc.add_friend(user_id=1, friend_username="alice")

# 接受好友请求
await svc.respond_to_request(user_id=3, friendship_id=5, accept=True)

# 获取好友列表
friends = await svc.get_friend_list(user_id=1)
```

---

## 6. 依赖关系

```
FriendService
├── SocialRepo (好友 CRUD)
├── UserRepository (用户名查询)
├── NotificationService (创建通知)
├── core.constants.MAX_FRIENDS
└── core.exceptions (统一异常)
```
