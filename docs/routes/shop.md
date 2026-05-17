# Shop Route

## 模块职责

`app/routes/shop.py` — 商店相关 API 端点（浏览种子、购买种子）。  
出售作物通过 `POST /api/farm/harvest` 处理。

## 设计决策

- 购买需要当前金币余额（从 `User` 模型的 `coins` 字段获取）
- 返回操作后剩余金币（`remaining_coins`）
- 错误处理通过全局 `AppError` 异常处理器统一拦截，不使用 `HTTPException`
- 路由前缀为 `/shop`，由 `main.py` 的 `include_router(..., prefix="/api")` 挂载到 `/api/shop`
- 认证通过 `session_token` Cookie（`get_current_user` 依赖），非 Bearer Token
- Schema 定义在 `app/schemas/shop.py`，不内联定义

## Python 实现

```python
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
```

## 路由列表

| 方法 | 路径 | 说明 |
|--------|-------------------|------|
| GET | /api/shop/seeds | 商店种子列表 |
| POST | /api/shop/buy | 购买种子 |

> 出售作物通过 `POST /api/farm/harvest` 处理（见 `routes/farm.md`）。

## 使用示例

```bash
# 查看商店种子列表
curl -b "session_token=<token>" http://localhost:8000/api/shop/seeds

# 购买 5 个小麦种子
curl -X POST -b "session_token=<token>" \
  -H "Content-Type: application/json" \
  -d '{"seed_type": "wheat", "quantity": 5}' \
  http://localhost:8000/api/shop/buy
```

## 完整买卖闭环

```
GET  /api/shop/seeds      → 查看种子清单（价格、解锁等级）
POST /api/shop/buy         → 购买种子（扣金币，加种子到背包）
GET  /api/farm/info        → 查看地块状态
POST /api/farm/plant       → 种植种子（消耗背包中的种子）
POST /api/farm/harvest     → 收获成熟作物（卖作物 = 收获，直接给金币 + XP）
```
