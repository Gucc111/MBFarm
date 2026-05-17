# Shop Route

## 模块职责

`app/api/routes/shop.py` — 商店相关 API 端点（购买商品、出售收获物）。

## 设计决策

- 购买/出售需要当前金币余额（从 User 模型获取）
- 返回操作后剩余金币
- 价格浮动逻辑在服务层预留

## Python 实现

```python
"""Shop API routes — buying and selling items."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.services.shop_service import ShopService, ShopServiceError

router = APIRouter(prefix="/api/shop", tags=["shop"])


def get_shop_service(db: AsyncSession = Depends(get_db)) -> ShopService:
    """依赖注入 ShopService。"""
    return ShopService(db)


# ------------------------------------------------------------------
# Request/Response Schemas (local, for simplicity)
# ------------------------------------------------------------------

class BuyRequest(BaseModel):
    crop_type: str = Field(..., min_length=1, max_length=32)
    quantity: int = Field(..., ge=1, le=100)


class BuyResponse(BaseModel):
    success: bool
    item_type: str
    item_subtype: str
    quantity: int
    total_cost: int
    remaining_gold: int


class SellRequest(BaseModel):
    crop_type: str = Field(..., min_length=1, max_length=32)
    quantity: int = Field(..., ge=1)


class SellResponse(BaseModel):
    success: bool
    crop_name: str
    quantity: int
    unit_price: int
    total_revenue: int
    new_gold: int


# ------------------------------------------------------------------
# Shop Endpoints
# ------------------------------------------------------------------

@router.get("/items")
async def list_shop_items(
    user: User = Depends(get_current_user),
):
    """获取商店全部可购商品列表。"""
    from app.services.shop_service import DEFAULT_SHOP_CONFIG
    items = [
        {
            "crop_type": crop_type,
            "buy_price": config["buy_price"],
            "sell_multiplier": config["sell_multiplier"],
        }
        for crop_type, config in DEFAULT_SHOP_CONFIG.items()
    ]
    return {"success": True, "items": items}


@router.post("/buy", response_model=BuyResponse)
async def buy_seeds(
    body: BuyRequest,
    user: User = Depends(get_current_user),
    service: ShopService = Depends(get_shop_service),
):
    """购买种子。"""
    try:
        result = await service.buy_seeds(
            user_id=user.id,
            crop_type=body.crop_type,
            quantity=body.quantity,
            gold=user.gold,
        )
        return result
    except ShopServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sell", response_model=SellResponse)
async def sell_harvest(
    body: SellRequest,
    user: User = Depends(get_current_user),
    service: ShopService = Depends(get_shop_service),
):
    """出售收获物。"""
    try:
        result = await service.sell_harvest(
            user_id=user.id,
            crop_type=body.crop_type,
            quantity=body.quantity,
            gold=user.gold,
        )
        return result
    except ShopServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## 路由列表

| 方法   | 路径              | 说明             |
|--------|-------------------|------------------|
| GET    | /api/shop/items   | 商品列表         |
| POST   | /api/shop/buy     | 购买种子         |
| POST   | /api/shop/sell    | 出售收获物       |

## 使用示例

```bash
# 购买 10 个小麦种子
curl -X POST -H "Authorization: Bearer <token>" \
  -d '{"crop_type": "wheat", "quantity": 10}' \
  http://localhost:8000/api/shop/buy

# 出售 3 个小麦收获物
curl -X POST -H "Authorization: Bearer <token>" \
  -d '{"crop_type": "wheat", "quantity": 3}' \
  http://localhost:8000/api/shop/sell
```
