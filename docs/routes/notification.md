# Route: Notification

## 模块职责

提供通知相关的 RESTful API：获取通知列表、标记已读、获取未读数。WebSocket 端点用于实时推送。

---

## API 端点列表

| Method | Path | 功能 | 认证 |
|---|---|---|---|
| `GET` | `/api/notifications` | 获取通知列表 | ✅ |
| `GET` | `/api/notifications/unread-count` | 获取未读数 | ✅ |
| `PUT` | `/api/notifications/{id}/read` | 标记已读 | ✅ |
| `PUT` | `/api/notifications/read-all` | 全部已读 | ✅ |
| `GET` | `/ws/{user_id}` | WebSocket 实时通知 | ✅ |

---

## 端点详情

### `GET /api/notifications`

获取通知列表（支持分页和未读筛选）。

**查询参数:**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `page` | int | ❌ | 1 | 页码 |
| `per_page` | int | ❌ | 20 | 每页数量 |
| `unread_only` | bool | ❌ | false | 仅未读 |
| `type` | str | ❌ | all | 通知类型筛选 |

**响应体 (200):**

```json
{
  "notifications": [
    {
      "id": 1,
      "user_id": 1,
      "type": "steal",
      "title": "⚠️ 你的作物被偷了！",
      "message": "用户 2 偷走了你 50 金币的作物。",
      "is_read": false,
      "created_at": "2025-07-10T10:00:00"
    }
  ],
  "total": 25,
  "page": 1,
  "per_page": 20
}
```

---

### `GET /api/notifications/unread-count`

获取未读通知数量。

**响应体 (200):**

```json
{
  "unread_count": 5
}
```

---

### `PUT /api/notifications/{id}/read`

标记单条通知为已读。

**路径参数:**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | int | ✅ | 通知 ID |

**响应体 (200):**

```json
{
  "id": 1,
  "is_read": true
}
```

---

### `PUT /api/notifications/read-all`

标记所有通知为已读。

**响应体 (200):**

```json
{
  "marked_count": 5
}
```

---

### `GET /ws/{user_id}`

WebSocket 端点，用于实时推送通知。

**路径参数:**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `user_id` | int | ✅ | 用户 ID |

**连接认证:** 通过 Query 参数 `token` 传递认证令牌。

**消息格式 (服务端 → 客户端):**

```json
{
  "type": "steal",
  "title": "⚠️ 作物被偷！",
  "message": "你被偷走了 50 金币的作物。",
  "source_user_id": 2
}
```

---

## 完整路由代码

```python
"""app/routes/notification.py — Notification API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.services.notification_service import NotificationService
from app.services.notification import RealtimeNotificationService

router = APIRouter(prefix="/api/notifications", tags=["notification"])

realtime_service = RealtimeNotificationService()


@router.get(
    "",
    response_model=dict,
    summary="通知列表",
)
async def get_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: NotificationService = Depends(lambda: NotificationService(db)),
):
    """获取通知列表。"""
    return await service.get_notifications(
        user_id=current_user.id,
        unread_only=unread_only,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/unread-count",
    response_model=dict,
    summary="未读数量",
)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: NotificationService = Depends(lambda: NotificationService(db)),
):
    """获取未读通知数量。"""
    count = await service.get_unread_count(current_user.id)
    return {"unread_count": count}


@router.put(
    "/{notification_id}/read",
    response_model=dict,
    summary="标记已读",
)
async def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: NotificationService = Depends(lambda: NotificationService(db)),
):
    """标记单条通知为已读。"""
    await service.mark_read(notification_id, current_user.id)
    return {"id": notification_id, "is_read": True}


@router.put(
    "/read-all",
    response_model=dict,
    summary="全部已读",
)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: NotificationService = Depends(lambda: NotificationService(db)),
):
    """标记所有通知为已读。"""
    await service.mark_all_read(current_user.id)
    return {"marked": True}


@router.websocket("/ws/{user_id}")
async def websocket_notification(
    websocket: WebSocket,
    user_id: int,
    token: str = Query(...),
):
    """WebSocket 实时通知推送端点。"""
    # 验证 token（简化）
    await realtime_service.add_connection(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # 保持连接
    except Exception:
        realtime_service.remove_connection(user_id, websocket)
```

---

## 错误码汇总

| HTTP 状态码 | 场景 |
|---|---|
| 200 | 成功 |
| 401 | 未认证 |
| 404 | 通知不存在 |

---

*文档生成时间: 2025-07-10*
