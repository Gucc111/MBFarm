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
    # Reuse BlockUserRequest schema (both have target_user_id)
    result = await svc.remove_friend(user.id, body.target_user_id)
    return ActionResponse(success=True, message="已解除好友关系", target_id=result["friend_id"])
