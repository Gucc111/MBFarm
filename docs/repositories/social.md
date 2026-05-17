# Social Repository

## 模块职责

`app/repositories/social_repo.py` — 社交关系的数据访问层（好友请求、好友列表）。

## 设计决策

- 有向关系操作：发送请求只创建 user_id→friend_id 的记录
- 双向确认：accept_request 方法创建 A→B 和 B→A 两条 accepted 记录
- 好友查询：`get_friends()` 查询 user_id→X 的 accepted 记录，由 service 层判断双向性
- 所有时间操作使用 `datetime.now(timezone.utc)`（UTC 时间）

## Python 实现

```python
"""Social repository — data access for friendships."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.social import Friendship, FriendshipStatus
from app.models.user import User


class SocialRepo:
    """社交关系的数据访问层。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Friendship CRUD
    # ------------------------------------------------------------------

    async def get_friendship(self, user_id: int, friend_id: int) -> Friendship | None:
        """获取单向好友关系。"""
        result = await self.db.execute(
            select(Friendship).where(
                Friendship.user_id == user_id,
                Friendship.friend_id == friend_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, friendship_id: int) -> Friendship | None:
        """根据 ID 获取好友关系。"""
        result = await self.db.execute(
            select(Friendship).where(Friendship.id == friendship_id)
        )
        return result.scalar_one_or_none()

    async def send_request(self, user_id: int, friend_id: int) -> Friendship:
        """发送好友请求（先检查是否有已有记录）。"""
        existing = await self.get_friendship(user_id, friend_id)
        if existing:
            if existing.status == FriendshipStatus.PENDING:
                raise ValueError("Friend request already pending")
            if existing.status == FriendshipStatus.ACCEPTED:
                raise ValueError("Already friends")
            if existing.status == FriendshipStatus.BLOCKED:
                raise ValueError("User is blocked")
            existing.status = FriendshipStatus.PENDING
            existing.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            return existing

        friendship = Friendship(user_id=user_id, friend_id=friend_id)
        self.db.add(friendship)
        await self.db.flush()
        await self.db.refresh(friendship)
        return friendship

    async def update_status(self, friendship_id: int, status: FriendshipStatus) -> Friendship:
        """更新好友关系状态。"""
        friendship = await self.get_by_id(friendship_id)
        if friendship is None:
            raise ValueError("Friendship not found")
        friendship.status = status
        friendship.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return friendship

    # ------------------------------------------------------------------
    # Response Operations
    # ------------------------------------------------------------------

    async def accept_request(self, requester_id: int, acceptor_id: int) -> None:
        """接受好友请求，创建双向 accepted 关系。"""
        req = await self.get_friendship(requester_id, acceptor_id)
        if not req or req.status != FriendshipStatus.PENDING:
            raise ValueError("No pending request found")
        req.status = FriendshipStatus.ACCEPTED
        req.updated_at = datetime.now(timezone.utc)

        reverse = await self.get_friendship(acceptor_id, requester_id)
        if reverse:
            if reverse.status == FriendshipStatus.PENDING:
                reverse.status = FriendshipStatus.ACCEPTED
                reverse.updated_at = datetime.now(timezone.utc)
        else:
            reverse = Friendship(
                user_id=acceptor_id,
                friend_id=requester_id,
                status=FriendshipStatus.ACCEPTED,
            )
            self.db.add(reverse)
        await self.db.flush()

    async def reject_request(self, requester_id: int, rejector_id: int) -> None:
        """拒绝好友请求。"""
        req = await self.get_friendship(requester_id, rejector_id)
        if not req or req.status != FriendshipStatus.PENDING:
            raise ValueError("No pending request found")
        req.status = FriendshipStatus.REJECTED
        req.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

    # ------------------------------------------------------------------
    # Query Operations
    # ------------------------------------------------------------------

    async def get_pending_received(self, user_id: int) -> list[Friendship]:
        """获取用户收到的待处理好友请求（含请求方用户信息）。"""
        result = await self.db.execute(
            select(Friendship)
            .options(selectinload(Friendship.user))
            .where(
                Friendship.friend_id == user_id,
                Friendship.status == FriendshipStatus.PENDING,
            )
        )
        return list(result.scalars().all())

    async def get_friends(self, user_id: int) -> list[Friendship]:
        """获取用户的所有 accepted 好友关系（user_id→X，含好友信息）。"""
        result = await self.db.execute(
            select(Friendship)
            .options(selectinload(Friendship.friend))
            .where(
                Friendship.user_id == user_id,
                Friendship.status == FriendshipStatus.ACCEPTED,
            )
        )
        return list(result.scalars().all())

    async def count_friends(self, user_id: int) -> int:
        """统计用户当前好友数量（outgoing accepted）。"""
        result = await self.db.execute(
            select(func.count(Friendship.id)).where(
                Friendship.user_id == user_id,
                Friendship.status == FriendshipStatus.ACCEPTED,
            )
        )
        return result.scalar_one()

    async def count_pending_received(self, user_id: int) -> int:
        """统计收到的待处理请求数。"""
        result = await self.db.execute(
            select(func.count(Friendship.id)).where(
                Friendship.friend_id == user_id,
                Friendship.status == FriendshipStatus.PENDING,
            )
        )
        return result.scalar_one()

    async def is_friend(self, user_id: int, other_id: int) -> bool:
        """检查两人是否互为好友（双向 accepted）。"""
        fwd = await self.get_friendship(user_id, other_id)
        if fwd and fwd.status == FriendshipStatus.ACCEPTED:
            bwd = await self.get_friendship(other_id, user_id)
            return bwd is not None and bwd.status == FriendshipStatus.ACCEPTED
        return False

    async def block_user(self, user_id: int, target_id: int) -> None:
        """拉黑用户。"""
        existing = await self.get_friendship(user_id, target_id)
        if existing:
            existing.status = FriendshipStatus.BLOCKED
            existing.updated_at = datetime.now(timezone.utc)
        else:
            existing = Friendship(
                user_id=user_id,
                friend_id=target_id,
                status=FriendshipStatus.BLOCKED,
            )
            self.db.add(existing)
        await self.db.flush()

    async def remove_friendship(self, user_id: int, friend_id: int) -> None:
        """解除好友关系（删除两条双向记录）。"""
        await self.db.execute(
            delete(Friendship).where(
                and_(
                    Friendship.user_id == user_id,
                    Friendship.friend_id == friend_id,
                )
            )
        )
        await self.db.execute(
            delete(Friendship).where(
                and_(
                    Friendship.user_id == friend_id,
                    Friendship.friend_id == user_id,
                )
            )
        )
        await self.db.flush()
```

## 方法汇总

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `get_friendship` | user_id, friend_id | `Friendship \| None` | 获取单向关系 |
| `get_by_id` | friendship_id | `Friendship \| None` | 按 ID 获取 |
| `send_request` | user_id, friend_id | `Friendship` | 发送/更新请求 |
| `update_status` | friendship_id, status | `Friendship` | 更新状态 |
| `accept_request` | requester_id, acceptor_id | `None` | 接受请求，创建双向 |
| `reject_request` | requester_id, rejector_id | `None` | 拒绝请求 |
| `get_pending_received` | user_id | `list[Friendship]` | 收到的待处理请求 |
| `get_friends` | user_id | `list[Friendship]` | accepted 好友列表 |
| `count_friends` | user_id | `int` | 好友数量 |
| `count_pending_received` | user_id | `int` | 待处理请求数 |
| `is_friend` | user_id, other_id | `bool` | 是否为双向好友 |
| `block_user` | user_id, target_id | `None` | 拉黑用户 |
| `remove_friendship` | user_id, friend_id | `None` | 解除双向关系 |

## 使用示例

```python
from app.repositories.social_repo import SocialRepo

# 发送好友请求
repo = SocialRepo(db)
await repo.send_request(user_id=1, friend_id=3)

# 接受好友请求
repo = SocialRepo(db)
await repo.accept_request(requester_id=1, acceptor_id=3)

# 获取好友列表
repo = SocialRepo(db)
friends = await repo.get_friends(user_id=1)

# 检查是否是好友
repo = SocialRepo(db)
is_friendly = await repo.is_friend(user_id=1, other_id=3)  # True
```
