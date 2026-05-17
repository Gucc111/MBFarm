# Farm Route

## 模块职责

`app/api/routes/farm.py` — 农场相关 API 端点（种植、收获、地块列表、解锁）。

## 设计决策

- 使用 FastAPI APIRouter 模块化路由
- 所有端点需要认证（通过 `get_current_user` 依赖注入）
- 依赖注入 FarmService 实例
- 统一响应格式（success + 数据/错误信息）

## Python 实现

```python
"""Farm API routes — planting, harvesting, plot management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.services.farm_service import FarmService, FarmServiceError

router = APIRouter(prefix="/api/farm", tags=["farm"])


def get_farm_service(db: AsyncSession = Depends(get_db)) -> FarmService:
    """依赖注入 FarmService。"""
    return FarmService(db)


# ------------------------------------------------------------------
# Plot Endpoints
# ------------------------------------------------------------------

@router.get("/plots")
async def get_plots(
    user: User = Depends(get_current_user),
    service: FarmService = Depends(get_farm_service),
):
    """获取用户所有地块。"""
    plots = await service.farm_repo.get_user_plots(user.id)
    return {
        "success": True,
        "plots": [
            {
                "id": p.id,
                "slot_index": p.slot_index,
                "is_locked": p.is_locked,
                "is_planted": p.is_planted,
                "crop": {
                    "id": p.crop.id,
                    "crop_type": p.crop.crop_type,
                    "planted_at": p.crop.plant_time.isoformat(),
                    "maturity_time": p.crop.maturity_time.isoformat(),
                    "is_mature": p.is_mature,
                    "harvested": p.crop.harvested,
                } if p.crop else None,
            }
            for p in plots
        ],
    }


@router.post("/plots/{plot_id}/unlock")
async def unlock_plot(
    plot_id: int,
    user: User = Depends(get_current_user),
    service: FarmService = Depends(get_farm_service),
):
    """解锁地块。"""
    try:
        result = await service.unlock_plot(user.id, plot_id)
        return {"success": True, "message": result["unlock_reward"]}
    except FarmServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------------
# Planting Endpoints
# ------------------------------------------------------------------

@router.post("/plots/{plot_id}/plant")
async def plant_crop(
    plot_id: int,
    crop_type: str,
    user: User = Depends(get_current_user),
    service: FarmService = Depends(get_farm_service),
):
    """在指定地块播种。"""
    try:
        crop = await service.plant(user.id, plot_id, crop_type)
        return {
            "success": True,
            "crop": {
                "id": crop.id,
                "crop_type": crop.crop_type,
                "growth_hours": crop.growth_hours,
                "maturity_time": crop.maturity_time.isoformat(),
            },
        }
    except FarmServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------------
# Harvesting Endpoints
# ------------------------------------------------------------------

@router.post("/crops/{crop_id}/harvest")
async def harvest_crop(
    crop_id: int,
    user: User = Depends(get_current_user),
    service: FarmService = Depends(get_farm_service),
):
    """收获作物。"""
    try:
        result = await service.harvest(user.id, crop_id)
        return {
            "success": True,
            "crop_type": result["crop_type"],
            "reward_seeds": result["reward_seeds"],
        }
    except FarmServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## 路由列表

| 方法   | 路径                            | 说明          |
|--------|---------------------------------|---------------|
| GET    | /api/farm/plots                 | 获取地块列表  |
| POST   | /api/farm/plots/{id}/unlock     | 解锁地块      |
| POST   | /api/farm/plots/{id}/plant      | 播种          |
| POST   | /api/farm/crops/{id}/harvest    | 收获作物      |

## 使用示例

```bash
# 获取地块
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/farm/plots

# 播种小麦
curl -X POST -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/farm/plots/1/plant?crop_type=wheat"

# 收获作物
curl -X POST -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/farm/crops/42/harvest"
```
