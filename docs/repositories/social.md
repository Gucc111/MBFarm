# Social Repository

## 模块职责

`app/repositories/social_repo.py` — 社交关系的数据访问层（好友请求、好友列表）。

## 设计决策

- 有向关系操作：发送请求只创建 user_id→friend_id 的记录
- 双向确认：accept 方法创建 A→B 和 B→A 两条 accepted 记录
- 好友查询：通过双向 accepted 记录确认真正的双向好友

## Python 实现

```python
"""Social repository — data access for friendships."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.social import Friendship, FriendshipStatus


class SocialRepo:
    """社交关系的数据访问层。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Friendship CRUD
    # ------------------------------------------------------------------

    async def get_friendship(
        self,
        user_id: int,
        friend_id: int,
    ) -> Friendship | None:
        """获取单向好友关系。"""
        result = await self.db.execute(
            select(Friendship).where(
                Friendship.user_id == user_id,
                Friendship.friend_id == friend_id,
            )
        )
        return result.scalar_one_or_none()

    async def send_request(
        self,
        user_id: int,
        friend_id: int,
    ) -> Friendship:
        """发送好友请求（先检查是否有已有记录）。"""
        existing = await self.get_friendship(user_id, friend_id)
        if existing:
            if existing.status == FriendshipStatus.PENDING:
                raise ValueError("Friend request already pending")
            if existing.status == FriendshipStatus.ACCEPTED:
                raise ValueError("Already friends")
            if existing.status == FriendshipStatus.BLOCKED:
                raise ValueError("User is blocked")
            # rejected 或其他状态，允许重新发送
            existing.status = FriendshipStatus.PENDING
            existing.updated_at = datetime.now()
            await self.db.flush()
            return existing

        friendship = Friendship(user_id=user_id, friend_id=friend_id)
        self.db.add(friendship)
        await self.db.flush()
        await self.db.refresh(friendship)
        return friendship

    # ------------------------------------------------------------------
    # Response Operations
    # ------------------------------------------------------------------

    async def accept_request(
        self,
        requester_id: int,
        acceptor_id: int,
    ) -> None:
        """接受好友请求，创建双向 accepted 关系。"""
        # 更新原请求为 accepted
        req = await self.get_friendship(requester_id, acceptor_id)
        if not req or req.status != FriendshipStatus.PENDING:
            raise ValueError("No pending request found")
        req.status = FriendshipStatus.ACCEPTED
        req.updated_at = datetime.now()

        # 检查反向记录是否存在
        reverse = await self.get_friendship(acceptor_id, requester_id)
        if reverse:
            if reverse.status in (FriendshipStatus.PENDING,):
                reverse.status = FriendshipStatus.ACCEPTED
                reverse.updated_at = datetime.now()
            # 如果已 accepted 则无需操作
        else:
            # 创建反向 accepted 记录
            reverse = Friendship(
                user_id=acceptor_id,
                friend_id=requester_id,
                status=FriendshipStatus.ACCEPTED,
            )
            self.db.add(reverse)

        await self.db.flush()

    async def reject_request(
        self,
        requester_id: int,
        rejector_id: int,
    ) -> None:
        """拒绝好友请求。"""
        req = await self.get_friendship(requester_id, rejector_id)
        if not req or req.status != FriendshipStatus.PENDING:
            raise ValueError("No pending request found")
        req.status = FriendshipStatus.REJECTED
        req.updated_at = datetime.now()
        await self.db.flush()

    # ------------------------------------------------------------------
    # Query Operations
    # ------------------------------------------------------------------

    async def get_pending_requests(self, user_id: int) -> list[Friendship]:
        """获取用户收到的待处理好友请求。"""
        result = await self.db.execute(
            select(Friendship)
            .options(selectinload(Friendship.user))
            .where(
                Friendship.friend_id == user_id,
                Friendship.status == FriendshipStatus.PENDING,
            )
        )
        return list(result.scalars().all())

    async def get_accepted_friends(self, user_id: int) -> list[Friendship]:
        """获取用户的所有 accepted 单向关系（包含自己发起和收到的）。"""
        result = await self.db.execute(
            select(Friendship)
            .options(selectinload(Friendship.user))
            .where(
                Friendship.status == FriendshipStatus.ACCEPTED,
                Friendship.friend_id == user_id,
            )
        )
        return list(result.scalars().all())

    async def get_mutual_friends(self, user_id: int) -> list:
        """获取真正的好友（双向 accepted 关系中的对方用户）。"""
        from app.models.user import User

        # 子查询：找出 user_id→X 且 X→user_id 都是 accepted 的 X
        result = await self.db.execute(
            select(User).join(
                Friendship, User.id == Friendship.user_id
            ).where(
                Friendship.friend_id == user_id,
                Friendship.status == FriendshipStatus.ACCEPTED,
            ).join(
                Friendship, Friendship.user_id == User.id
            ).where(
                Friendship.friend_id == user_id,
                Friendship.status == FriendshipStatus.ACCEPTED,
            )
        )
        return list(result.scalars().all())

    async def is_friend(self, user_id: int, other_id: int) -> bool:
        """检查两人是否互为好友（双向 accepted）。"""
        fwd = await self.get_friendship(user_id, other_id)
        if fwd and fwd.status == FriendshipStatus.ACCEPTED:
            bwd = await self.get_friendship(other_id, user_id)
            return bwd and bwd.status == FriendshipStatus.ACCEPTED
        return False

    async def block_user(self, user_id: int, target_id: int) -> None:
        """拉黑用户。"""
        existing = await self.get_friendship(user_id, target_id)
        if existing:
            existing.status = FriendshipStatus.BLOCKED
            existing.updated_at = datetime.now()
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
                Friendship.user_id == user_id,
                Friendship.friend_id == friend_id,
            )
        )
        await self.db.execute(
            delete(Friendship).where(
                Friendship.user_id == friend_id,
                Friendship.friend_id == user_id,
            )
        )
        await self.db.flush()
```

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
friends = await repo.get_mutual_friends(user_id=1)

# 检查是否是好友
repo = SocialRepo(db)
is_friendly = await repo.is_friend(user_id=1, other_id=3)  # True
```
