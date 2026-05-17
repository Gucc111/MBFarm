# Route: Leaderboard

## 模块职责

提供排行榜相关的 RESTful API：获取排行榜列表、获取个人排名。

---

## API 端点列表

| Method | Path | 功能 | 认证 |
|---|---|---|---|
| `GET` | `/api/leaderboard` | 获取排行榜列表 | ✅ |
| `GET` | `/api/leaderboard/me` | 获取个人排名 | ✅ |

---

## 端点详情

### `GET /api/leaderboard`

获取排行榜列表（分页）。

**查询参数:**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `type` | str | ✅ | - | 排行类型: wealth, crop_count, steal_count, achievement_count |
| `page` | int | ❌ | 1 | 页码 |
| `per_page` | int | ❌ | 10 | 每页数量 (1-100) |

**响应体 (200):**

```json
{
  "type": "wealth",
  "entries": [
    {
      "rank": 1,
      "user_id": 2,
      "username": "farm_master",
      "score": 15000,
      "label": "¥15,000"
    },
    {
      "rank": 2,
      "user_id": 1,
      "username": "new_farmer",
      "score": 8500,
      "label": "¥8,500"
    }
  ],
  "total": 12,
  "page": 1,
  "per_page": 10
}
```

---

### `GET /api/leaderboard/me`

获取当前用户在排行榜中的排名。

**查询参数:**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `type` | str | ✅ | - | 排行类型 |

**响应体 (200):**

```json
{
  "user_id": 1,
  "username": "new_farmer",
  "rank": 2,
  "score": 8500,
  "total_players": 12
}
```

---

## 完整路由代码

```python
"""app/routes/leaderboard.py — Leaderboard API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.leaderboard import LeaderboardType
from app.services.leaderboard import LeaderboardService

router = APIRouter(prefix="/api", tags=["leaderboard"])


@router.get(
    "/leaderboard",
    response_model=dict,
    summary="排行榜",
)
async def get_leaderboard(
    lb_type: LeaderboardType = Query(..., description="排行类型"),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    service: LeaderboardService = Depends(lambda: LeaderboardService(db)),
):
    """获取排行榜列表。"""
    return await service.get_leaderboard(
        lb_type=lb_type,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/leaderboard/me",
    response_model=dict,
    summary="我的排名",
)
async def get_my_rank(
    lb_type: LeaderboardType = Query(..., description="排行类型"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: LeaderboardService = Depends(lambda: LeaderboardService(db)),
):
    """获取当前用户排名。"""
    return await service.get_user_rank(
        lb_type=lb_type,
        user_id=current_user.id,
    )
```

---

## 错误码汇总

| HTTP 状态码 | 场景 |
|---|---|
| 200 | 成功 |
| 400 | 参数错误 |
| 401 | 未认证 |

---

*文档生成时间: 2025-07-10*
