"""Farm API routes — plant, water, harvest, unlock, inventory."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.farm import (
    FarmInfoResponse,
    HarvestRequest,
    HarvestResult,
    PlantRequest,
    PlotResponse,
    UnlockResult,
    WaterRequest,
    WaterResult,
)
from app.schemas.item import (
    InventoryItem,
    InventoryResponse,
)
from app.services.farm_service import FarmService

router = APIRouter(prefix="/farm", tags=["农场"])


def _get_service(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FarmService:
    return FarmService(db, user.id)


# ── 种植 / 浇水 / 收获 ────────────────────────────────────────────────────────


@router.post(
    "/plant",
    response_model=PlotResponse,
    status_code=status.HTTP_200_OK,
    summary="种植作物",
)
async def plant(
    body: PlantRequest,
    svc: FarmService = Depends(_get_service),
):
    crop = await svc.plant(body.plot_index, body.seed_type)
    return svc._make_plot_response(crop.plot)  # type: ignore[attr-defined]


@router.post(
    "/water",
    response_model=WaterResult,
    status_code=status.HTTP_200_OK,
    summary="浇水",
)
async def water(
    body: WaterRequest,
    svc: FarmService = Depends(_get_service),
):
    return await svc.water(body.plot_index)


@router.post(
    "/harvest",
    response_model=HarvestResult,
    status_code=status.HTTP_200_OK,
    summary="收获作物",
)
async def harvest(
    body: HarvestRequest,
    svc: FarmService = Depends(_get_service),
):
    return await svc.harvest(body.plot_index)


# ── 解锁 / 农场信息 ──────────────────────────────────────────────────────────


@router.post(
    "/unlock",
    response_model=UnlockResult,
    status_code=status.HTTP_200_OK,
    summary="解锁新地块",
)
async def unlock_plot(
    svc: FarmService = Depends(_get_service),
):
    return await svc.unlock_plot()


@router.get(
    "/info",
    response_model=FarmInfoResponse,
    summary="获取农场完整信息",
)
async def farm_info(
    svc: FarmService = Depends(_get_service),
):
    return await svc.get_farm_info_response()


# ── 背包 ───────────────────────────────────────────────────────────────────────

@router.get(
    "/inventory",
    response_model=InventoryResponse,
    summary="获取背包",
)
async def inventory(
    svc: FarmService = Depends(_get_service),
):
    items = await svc.farm_repo.get_user_inventory(svc.user_id)
    user = await svc.user_repo.get_by_id(svc.user_id)
    return InventoryResponse(
        items=[InventoryItem.model_validate(i) for i in items],
        total_coins=user.coins if user else 0,
    )
