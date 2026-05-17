# Route: Admin

## 模块职责

管理后台 API 端点：用户管理、作物管理、数据统计、系统消息。

---

## API 端点列表

| Method | Path | 功能 | 认证 |
|---|---|---|---|
| `GET` | `/api/admin/users` | 用户列表 | ✅ 管理员 |
| `PUT` | `/api/admin/users/{id}` | 编辑用户 | ✅ 管理员 |
| `DELETE` | `/api/admin/users/{id}` | 删除用户 | ✅ 管理员 |
| `GET` | `/api/admin/stats` | 数据统计 | ✅ 管理员 |
| `POST` | `/api/admin/messages` | 发送系统消息 | ✅ 管理员 |
| `GET` | `/api/admin/leaderboard` | 排行榜管理 | ✅ 管理员 |

---

## 端点详情

### `GET /api/admin/users`

用户列表（分页）。

**查询参数:**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `page` | int | ❌ | 1 | 页码 |
| `per_page` | int | ❌ | 20 | 每页数量 |
| `search` | str | ❌ | - | 搜索用户名 |

**响应体 (200):**

```json
{
  "users": [
    {
      "id": 1,
      "username": "farm_master",
      "email": "farm@example.com",
      "gold": 15000,
      "created_at": "2025-07-01T00:00:00"
    }
  ],
  "total": 12,
  "page": 1,
  "per_page": 20
}
```

---

### `PUT /api/admin/users/{id}`

编辑用户信息。

**请求体:**

```json
{
  "username": "new_name",
  "gold": 5000
}
```

---

### `DELETE /api/admin/users/{id}`

删除用户。

**响应体 (200):**

```json
{
  "deleted": true,
  "user_id": 1
}
```

---

### `GET /api/admin/stats`

平台数据统计。

**响应体 (200):**

```json
{
  "total_users": 12,
  "active_users_today": 8,
  "total_crops_planted": 150,
  "total_crops_harvested": 100,
  "total_steals": 45,
  "total_notifications": 200
}
```

---

### `POST /api/admin/messages`

发送系统消息给所有用户。

**请求体:**

```json
{
  "title": "系统维护通知",
  "message": "系统将于今晚 12 点进行维护。"
}
```

---

## 完整路由代码

```python
"""app/routes/admin.py — Admin API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.core.exceptions import NotFound, PermissionDenied
from app.models.user import User
from app.models.crop import Crop
from app.models.stolen_crop import StolenCrop
from app.models.notification import Notification
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class AdminUserUpdate(BaseModel):
    """管理员编辑用户请求。"""
    username: Optional[str] = None
    gold: Optional[int] = None
    is_admin: Optional[bool] = None


class SystemMessageRequest(BaseModel):
    """系统消息请求。"""
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)


class AdminStatsResponse(BaseModel):
    """平台统计数据。"""
    total_users: int
    active_users_today: int
    total_crops_planted: int
    total_crops_harvested: int
    total_steals: int
    total_notifications: int


# ------------------------------------------------------------------
# 依赖注入
# ------------------------------------------------------------------

async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """验证管理员权限。"""
    if not current_user.is_admin:
        raise PermissionDenied("需要管理员权限。")
    return current_user


# ------------------------------------------------------------------
# 用户管理
# ------------------------------------------------------------------

@router.get(
    "/users",
    response_model=dict,
    summary="用户列表",
)
async def get_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    """获取用户列表。"""
    query = select(User)
    if search:
        query = query.where(User.username.contains(search))

    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    users = result.scalars().all()

    count_query = select(func.count()).select_from(User)
    if search:
        count_query = count_query.where(User.username.contains(search))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "gold": getattr(u, "gold", 0),
                "is_admin": u.is_admin,
                "created_at": u.created_at,
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.put(
    "/users/{user_id}",
    response_model=dict,
    summary="编辑用户",
)
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    """编辑用户信息。"""
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        raise NotFound("用户不存在。")

    if data.username is not None:
        user.username = data.username
    if data.gold is not None:
        from app.services.economy import EconomyService
        economy = EconomyService(db)
        await economy.update_gold(user_id, data.gold - (getattr(user, "gold", 0)))
    if data.is_admin is not None:
        user.is_admin = data.is_admin

    await db.flush()
    return {"updated": True, "user_id": user_id}


@router.delete(
    "/users/{user_id}",
    response_model=dict,
    summary="删除用户",
)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    """删除用户。"""
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        raise NotFound("用户不存在。")

    await db.delete(user)
    await db.flush()
    return {"deleted": True, "user_id": user_id}


# ------------------------------------------------------------------
# 数据统计
# ------------------------------------------------------------------

@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="数据统计",
)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    """获取平台统计数据。"""
    from datetime import datetime, timedelta

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    total_users_q = await db.execute(select(func.count()).select_from(User))
    active_users_q = await db.execute(
        select(func.count()).where(User.last_login_at >= yesterday)
    )
    total_planted_q = await db.execute(
        select(func.count()).select_from(Crop)
    )
    total_harvested_q = await db.execute(
        select(func.count()).where(Crop.status == "harvested")
    )
    total_steals_q = await db.execute(select(func.count()).select_from(StolenCrop))
    total_notifs_q = await db.execute(select(func.count()).select_from(Notification))

    return AdminStatsResponse(
        total_users=total_users_q.scalar() or 0,
        active_users_today=active_users_q.scalar() or 0,
        total_crops_planted=total_planted_q.scalar() or 0,
        total_crops_harvested=total_harvested_q.scalar() or 0,
        total_steals=total_steals_q.scalar() or 0,
        total_notifications=total_notifs_q.scalar() or 0,
    )


# ------------------------------------------------------------------
# 系统消息
# ------------------------------------------------------------------

@router.post(
    "/messages",
    response_model=dict,
    summary="发送系统消息",
)
async def send_system_message(
    data: SystemMessageRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    """发送系统消息给所有用户。"""
    from app.services.notification_service import NotificationService

    # 获取所有用户
    result = await db.execute(select(User.id))
    user_ids = result.scalars().all()

    notif_service = NotificationService(db)
    sent_count = 0
    for user_id in user_ids:
        await notif_service.create_notification(
            user_id=user_id,
            type="system",
            title=data.title,
            message=data.message,
        )
        sent_count += 1

    await db.flush()
    return {
        "sent": True,
        "sent_to": sent_count,
        "title": data.title,
    }
```

---

## 错误码汇总

| HTTP 状态码 | 场景 |
|---|---|
| 200 | 成功 |
| 401 | 未认证 |
| 403 | 非管理员 |
| 404 | 资源不存在 |

---

*文档生成时间: 2025-07-10*
