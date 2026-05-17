"""Steal API routes — steal crops from friends."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.steal import StealHistoryResponse, StealResult
from app.services.steal import StealService

router = APIRouter(prefix="/steal", tags=["偷菜"])


def _get_service(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StealService:
    return StealService(db)


@router.post(
    "/{target_user_id}",
    response_model=StealResult,
    status_code=status.HTTP_200_OK,
    summary="偷菜",
)
async def steal_crop(
    target_user_id: int,
    svc: StealService = Depends(_get_service),
    user: User = Depends(get_current_user),
):
    """偷取目标用户的成熟作物。"""
    return await svc.steal(user.id, target_user_id)


@router.get(
    "/my",
    response_model=StealHistoryResponse,
    summary="我偷了谁的",
)
async def get_my_stolen(
    svc: StealService = Depends(_get_service),
    user: User = Depends(get_current_user),
):
    """查看我偷了谁的作物。"""
    return await svc.get_my_stolen(user.id)


@router.get(
    "/me",
    response_model=StealHistoryResponse,
    summary="谁偷了我",
)
async def get_being_stolen(
    svc: StealService = Depends(_get_service),
    user: User = Depends(get_current_user),
):
    """查看谁偷了我。"""
    return await svc.get_being_stolen(user.id)
