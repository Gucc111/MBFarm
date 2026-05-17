# Route: Steal

## 模块职责

提供偷菜相关的 RESTful API：执行偷菜、查看偷菜记录、查看被偷记录。

---

## API 端点列表

| Method | Path | 功能 | 认证 |
|---|---|---|---|
| `POST` | `/api/steal/{target_user_id}` | 偷取目标用户作物 | ✅ |
| `GET` | `/api/steal/my` | 查看我偷了谁的 | ✅ |
| `GET` | `/api/steal/me` | 查看谁偷了我 | ✅ |

---

## 端点详情

### `POST /api/steal/{target_user_id}`

偷取目标用户的成熟作物。

**路径参数:**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `target_user_id` | int | ✅ | 目标用户 ID |

**查询参数:**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `plot_index` | int | ❌ | 指定偷哪个 plot（1-25），None = 随机 |

**请求体:** 无

**响应体 (200):**

```json
{
  "stolen_amount": 50,
  "remaining_amount": 50,
  "stealer_user_id": 1,
  "victim_user_id": 2,
  "message": "偷成功！获得 50 金币。"
}
```

**错误响应:**

| 状态码 | 错误信息 |
|---|---|
| 403 | 不能偷自己 |
| 404 | 目标无成熟作物 |
| 429 | 冷却中 / 每日上限 |

---

### `GET /api/steal/my`

查看我偷了谁的作物（分页）。

**查询参数:**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `page` | int | ❌ | 1 | 页码 |
| `per_page` | int | ❌ | 20 | 每页数量 |

**响应体 (200):**

```json
{
  "records": [
    {
      "id": 1,
      "stealer_id": 1,
      "victim_id": 2,
      "amount": 50,
      "stolen_at": "2025-07-10T10:00:00"
    }
  ],
  "total": 15,
  "page": 1,
  "per_page": 20
}
```

---

### `GET /api/steal/me`

查看谁偷了我。

**响应体 (200):**

```json
{
  "stolen_by": [
    {
      "stealer_id": 2,
      "amount": 50,
      "stolen_at": "2025-07-10T10:00:00"
    }
  ],
  "total": 3
}
```

---

## 完整路由代码

```python
"""app/routes/steal.py — Steal crop API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.services.steal import StealService
from app.schemas.steal import StealResult, StolenCropRecord

router = APIRouter(prefix="/api/steal", tags=["steal"])


@router.post(
    "/{target_user_id}",
    response_model=StealResult,
    summary="偷菜",
    status_code=200,
)
async def steal_crop(
    target_user_id: int,
    plot_index: int | None = Query(None, ge=1, le=25),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: StealService = Depends(lambda: StealService(db)),
):
    """偷取目标用户的成熟作物。"""
    return await service.steal(
        user_id=current_user.id,
        target_user_id=target_user_id,
        plot_index=plot_index,
    )


@router.get(
    "/my",
    response_model=dict,
    summary="我偷了谁的",
)
async def get_my_stolen(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: StealService = Depends(lambda: StealService(db)),
):
    """查看我偷了谁的作物。"""
    return await service.get_stolen_crops(
        user_id=current_user.id,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/me",
    response_model=dict,
    summary="谁偷了我",
)
async def get_being_stolen(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: StealService = Depends(lambda: StealService(db)),
):
    """查看谁偷了我。"""
    records = await service.get_being_stolen(user_id=current_user.id)
    return {
        "stolen_by": records,
        "total": len(records),
    }
```

---

## 错误码汇总

| HTTP 状态码 | 场景 |
|---|---|
| 200 | 偷菜成功 |
| 400 | 参数错误 / 冷却中 / 每日上限 |
| 401 | 未认证 |
| 403 | 偷自己 |
| 404 | 无成熟作物 |
| 429 | 频率限制 |

---

*文档生成时间: 2025-07-10*
