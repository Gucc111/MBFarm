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
        """获取用户的所有双向 accepted 好友关系（含好友信息）。"""
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
        """统计用户当前好友数量（双向 accepted）。"""
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
