# Route: Achievement

## 模块职责

提供成就相关的 RESTful API：获取成就列表、检查并解锁成就、获取单个成就详情。

---

## API 端点列表

| Method | Path | 功能 | 认证 |
|---|---|---|---|
| `GET` | `/api/achievements` | 获取我的成就列表 | ✅ |
| `GET` | `/api/achievements/{achievement_id}` | 获取单个成就详情 | ✅ |
| `POST` | `/api/achievements/check` | 检查并解锁新成就 | ✅ |
| `GET` | `/api/achievements/all` | 获取所有成就定义 | ❌ |

---

## 端点详情

### `GET /api/achievements`

获取当前用户已解锁的成就列表。

**查询参数:**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `page` | int | ❌ | 1 | 页码 |
| `per_page` | int | ❌ | 20 | 每页数量 |

**响应体 (200):**

```json
[
  {
    "id": 1,
    "user_id": 1,
    "achievement_id": "first_harvest",
    "status": "unlocked",
    "unlocked_at": "2025-07-10T10:00:00"
  }
]
```

---

### `GET /api/achievements/{achievement_id}`

获取单个成就的解锁状态。

**路径参数:**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `achievement_id` | str | ✅ | 成就 ID（如 `first_plant`） |

**响应体 (200):**

```json
{
  "id": 1,
  "user_id": 1,
  "achievement_id": "first_plant",
  "status": "unlocked",
  "unlocked_at": "2025-07-10T10:00:00"
}
```

**错误响应:**

| 状态码 | 说明 |
|---|---|
| 404 | 成就不存在 / 未解锁 |

---

### `POST /api/achievements/check`

手动触发检查并解锁新成就（通常在收获/种植后调用）。

**响应体 (200):**

```json
{
  "newly_unlocked": [
    {
      "id": "rich",
      "name": "小有积蓄",
      "desc": "金币达到 1,000",
      "icon": "💰"
    }
  ]
}
```

---

### `GET /api/achievements/all`

获取所有成就的定义信息（含当前用户的解锁状态）。

**响应体 (200):**

```json
[
  {
    "id": "first_plant",
    "name": "初出茅庐",
    "desc": "首次种植作物",
    "icon": "🌱",
    "unlocked": true
  },
  {
    "id": "rich",
    "name": "小有积蓄",
    "desc": "金币达到 1,000",
    "icon": "💰",
    "unlocked": false
  }
]
```

---

## 完整路由代码

```python
"""app/routes/achievement.py — Achievement API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.services.achievement import AchievementService
from app.schemas.achievement import AchievementInfo

router = APIRouter(prefix="/api/achievements", tags=["achievement"])


@router.get(
    "",
    response_model=list,
    summary="我的成就",
)
async def get_my_achievements(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AchievementService = Depends(lambda: AchievementService(db)),
):
    """获取当前用户已解锁的成就。"""
    return await service.get_user_achievements(
        user_id=current_user.id,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/{achievement_id}",
    response_model=dict,
    summary="单个成就",
)
async def get_achievement(
    achievement_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AchievementService = Depends(lambda: AchievementService(db)),
):
    """获取单个成就详情。"""
    record = await service.get_achievement(achievement_id, current_user.id)
    if not record:
        return {"found": False, "achievement_id": achievement_id}
    return {"found": True, "record": record}


@router.post(
    "/check",
    response_model=dict,
    summary="检查并解锁成就",
)
async def check_achievements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AchievementService = Depends(lambda: AchievementService(db)),
):
    """检查并解锁新成就。"""
    newly_unlocked = await service.check_all(current_user.id)
    return {
        "newly_unlocked": [
            {
                "id": a.id,
                "name": a.name,
                "desc": a.desc,
                "icon": a.icon,
            }
            for a in newly_unlocked
        ]
    }


@router.get(
    "/all",
    response_model=list,
    summary="所有成就定义",
)
async def get_all_achievements(
    current_user: User | None = Depends(get_current_user),  # 可选认证
    db: AsyncSession = Depends(get_db),
    service: AchievementService = Depends(lambda: AchievementService(db)),
):
    """获取所有成就定义（含当前用户解锁状态）。"""
    user_id = current_user.id if current_user else None
    all_info = await service.get_all_achievements_info()
    return all_info
```

---

## 错误码汇总

| HTTP 状态码 | 场景 |
|---|---|
| 200 | 成功 |
| 401 | 未认证（需要认证的端点） |
| 404 | 成就不存在 |

---

*文档生成时间: 2025-07-10*
