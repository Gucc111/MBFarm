"""Shop API routes — buying seeds and browsing the shop."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.shop import BuySeedRequest, BuySeedResponse, ShopListResponse
from app.services.shop import ShopService

router = APIRouter(prefix="/shop", tags=["商店"])


# ── Factory ──────────────────────────────────────────────────────────────────

def _get_service(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ShopService:
    return ShopService(db, user.id)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/seeds",
    response_model=ShopListResponse,
    summary="商店种子列表",
)
async def shop_seeds(
    svc: ShopService = Depends(_get_service),
):
    """获取商店种子列表（含用户金币、等级）。"""
    data = await svc.get_shop_list()

    from app.schemas.shop import ShopItem

    seeds = [
        ShopItem(
            seed_type=s["seed_type"],
            name=s["name"],
            buy_price=s["buy_price"],
            sell_price=s["sell_price"],
            unlock_level=s["unlock_level"],
            grow_time=s["grow_time"],
        )
        for s in data["seeds"]
    ]

    return ShopListResponse(seeds=seeds, user_coins=data["user_coins"])


@router.post(
    "/buy",
    response_model=BuySeedResponse,
    status_code=status.HTTP_200_OK,
    summary="购买种子",
)
async def buy_seeds(
    body: BuySeedRequest,
    svc: ShopService = Depends(_get_service),
):
    """购买种子：消耗金币，增加背包种子库存。"""
    result = await svc.buy_seeds(body.seed_type, body.quantity)
    return BuySeedResponse(**result)
