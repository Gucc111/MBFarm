# Farm Route

## 模块职责

`app/routes/farm.py` — 农场相关 API 端点（种植、浇水、收获、解锁、商店、背包）。

## 设计决策

- 使用 FastAPI APIRouter 模块化路由
- 所有端点需要认证（通过 `get_current_user` 依赖注入）
- 通过 `_get_service()` 依赖注入 `FarmService` 实例（绑定当前用户）
- 使用 Pydantic `response_model` 统一响应格式
- 异常由全局异常处理器 `app_error_handler` 统一处理

## 路由列表

| 方法 | 路径 | 说明 | 请求 Schema | 响应 Schema |
|------|------|------|-------------|-------------|
| POST | `/api/farm/plant` | 种植作物 | `PlantRequest` | `PlotResponse` |
| POST | `/api/farm/water` | 浇水 | `WaterRequest` | `WaterResult` |
| POST | `/api/farm/harvest` | 收获作物 | `HarvestRequest` | `HarvestResult` |
| POST | `/api/farm/unlock` | 解锁新地块 | — | `UnlockResult` |
| GET | `/api/farm/info` | 获取农场完整信息 | — | `FarmInfoResponse` |
| GET | `/api/farm/shop/seeds` | 商店种子列表 | — | `ShopResponse` |
| POST | `/api/farm/shop/buy` | 购买种子 | `BuySeedRequest` | dict |
| GET | `/api/farm/inventory` | 获取背包 | — | `InventoryResponse` |

## 完整 Python 实现

```python
"""Farm API routes — plant, water, harvest, unlock, shop, inventory."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import AppValidationError
from app.models.user import User
from app.schemas.farm import (
    FarmInfoResponse, HarvestRequest, HarvestResult, PlantRequest,
    PlotResponse, UnlockResult, WaterRequest, WaterResult,
)
from app.schemas.item import (
    BuySeedRequest, InventoryItem, InventoryResponse, ShopItem, ShopResponse,
)
from app.services.farm_service import FarmService

router = APIRouter(prefix="/farm", tags=["农场"])


def _get_service(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FarmService:
    return FarmService(db, user.id)


# ── 种植 / 浇水 / 收获 ─────────────────────────────────────────────

@router.post("/plant", response_model=PlotResponse, status_code=200, summary="种植作物")
async def plant(body: PlantRequest, svc: FarmService = Depends(_get_service)):
    crop = await svc.plant(body.plot_index, body.seed_type)
    return svc._make_plot_response(crop.plot)


@router.post("/water", response_model=WaterResult, status_code=200, summary="浇水")
async def water(body: WaterRequest, svc: FarmService = Depends(_get_service)):
    return await svc.water(body.plot_index)


@router.post("/harvest", response_model=HarvestResult, status_code=200, summary="收获作物")
async def harvest(body: HarvestRequest, svc: FarmService = Depends(_get_service)):
    return await svc.harvest(body.plot_index)


# ── 解锁 / 农场信息 ──────────────────────────────────────────────

@router.post("/unlock", response_model=UnlockResult, status_code=200, summary="解锁新地块")
async def unlock_plot(svc: FarmService = Depends(_get_service)):
    return await svc.unlock_plot()


@router.get("/info", response_model=FarmInfoResponse, summary="获取农场完整信息")
async def farm_info(svc: FarmService = Depends(_get_service)):
    return await svc.get_farm_info_response()


# ── 商店 / 背包 ──────────────────────────────────────────────────

@router.get("/shop/seeds", response_model=ShopResponse, summary="商店种子列表")
async def shop_seeds():
    from app.core.constants import SEEDS
    seeds = [
        ShopItem(
            id=s.id, name=s.name, price=s.buy_price, sell_price=s.sell_price,
            grow_time=s.grow_time, xp_reward=s.xp_reward,
            unlock_level=s.unlock_level, water_bonus=s.water_bonus,
        )
        for s in SEEDS
    ]
    return ShopResponse(seeds=seeds)


@router.post("/shop/buy", summary="购买种子")
async def buy_seed(body: BuySeedRequest, svc: FarmService = Depends(_get_service)):
    from app.core.constants import SEED_MAP
    seed = SEED_MAP.get(body.seed_type)
    if seed is None:
        raise AppValidationError(f"未知的种子类型: {body.seed_type}")

    cost = seed.buy_price * body.quantity
    user = await svc.user_repo.get_by_id(svc.user_id)
    if user.coins < cost:
        raise AppValidationError(f"金币不足（需要 {cost}，当前 {user.coins}）")

    user.coins -= cost
    await svc.farm_repo.add_item(svc.user_id, "seed", body.seed_type, body.quantity)
    user.last_active_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    await svc.db.flush()

    return {"message": f"购买了 {body.quantity} 个 {seed.name}", "remaining_coins": user.coins}


@router.get("/inventory", response_model=InventoryResponse, summary="获取背包")
async def inventory(svc: FarmService = Depends(_get_service)):
    items = await svc.farm_repo.get_user_inventory(svc.user_id)
    user = await svc.user_repo.get_by_id(svc.user_id)
    return InventoryResponse(
        items=[InventoryItem.model_validate(i) for i in items],
        total_coins=user.coins if user else 0,
    )
```

## 使用示例

```bash
# 获取农场信息
curl -b "session_token=xxx" http://localhost:8000/api/farm/info

# 种植小麦
curl -X POST -b "session_token=xxx" \
  -H "Content-Type: application/json" \
  -d '{"plot_index": 1, "seed_type": "wheat"}' \
  http://localhost:8000/api/farm/plant

# 浇水
curl -X POST -b "session_token=xxx" \
  -H "Content-Type: application/json" \
  -d '{"plot_index": 1}' \
  http://localhost:8000/api/farm/water

# 收获
curl -X POST -b "session_token=xxx" \
  -H "Content-Type: application/json" \
  -d '{"plot_index": 1}' \
  http://localhost:8000/api/farm/harvest

# 购买种子
curl -X POST -b "session_token=xxx" \
  -H "Content-Type: application/json" \
  -d '{"seed_type": "wheat", "quantity": 10}' \
  http://localhost:8000/api/farm/shop/buy

# 查看背包
curl -b "session_token=xxx" http://localhost:8000/api/farm/inventory
```

## 错误处理

所有错误通过全局异常处理器返回统一格式：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "体力不足（需要 5，当前 2）"
  }
}
```

| 场景 | 异常类 | HTTP 状态码 |
|------|--------|-------------|
| 地块已有作物 | `ConflictError` | 409 |
| 地块不存在/无作物 | `NotFoundError` | 404 |
| 体力不足/未成熟/种子不足 | `AppValidationError` | 422 |
| 未登录 | `UnauthorizedError` | 401 |
