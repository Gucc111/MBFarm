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
        if friend_count >= SYSTEM.max_friends:
            raise ConflictError(f"好友已达上限 ({SYSTEM.max_friends})")

        friendship = await self.social_repo.send_request(user_id, target.id)

        # TODO: 通知系统上线后添加
        # await self.notif_service.create(...)

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
