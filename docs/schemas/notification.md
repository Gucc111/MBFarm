# 通知模块 Pydantic Schema

> 定义通知系统的 Pydantic 数据验证模型，对应 `app/schemas/notification.py`。

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **通知列表分页** | 提供分页通知列表响应 |
| **未读数统计** | 返回未读通知数量 |
| **WebSocket 载荷** | 定义 WebSocket 实时推送的消息格式 |
| **标记已读** | 处理通知已读标记请求 |

---

## 2. Schema 列表

| Schema 类名 | 用途 | 方向 |
|------------|------|------|
| `NotificationResponse` | 单条通知信息 | 响应 |
| `NotificationListResponse` | 分页通知列表 | 响应 |
| `NotificationCountResponse` | 未读数量 | 响应 |
| `MarkReadRequest` | 标记已读请求 | 请求体 |
| `WSNotificationPayload` | WebSocket 推送载荷 | WS 消息 |
| `WSMessageEnvelope` | WebSocket 消息信封 | WS 消息 |

---

## 3. 字段校验规则

| Schema | 字段 | 类型 | 校验规则 |
|--------|------|------|----------|
| MarkReadRequest | `notification_id` | int | `ge=1` |
| MarkReadRequest | `batch` | list[int] | 单次最多 100 条 |
| WSNotificationPayload | `type` | str | 枚举值校验 |
| WSNotificationPayload | `data` | dict | 按 type 动态结构 |

---

## 4. 完整实现代码

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    """单条通知信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str                        # steal / friend_request / crop_mature / system / achievement
    title: str
    message: str
    from_user_id: int | None = None
    from_username: str | None = None
    is_read: bool = False
    created_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "type": "steal",
                "title": "有人偷了你的菜！",
                "message": "张三偷走了你的 2 个小麦",
                "from_user_id": 5,
                "from_username": "张三",
                "is_read": False,
                "created_at": "2024-01-15T10:30:00Z",
            }
        }


class NotificationListResponse(BaseModel):
    """分页通知列表"""
    notifications: list[NotificationResponse]
    total: int
    page: int = 1
    per_page: int = 20
    unread_count: int = 0


class NotificationCountResponse(BaseModel):
    """未读通知数量"""
    unread_count: int = Field(ge=0, description="未读通知数量")


class MarkReadRequest(BaseModel):
    """标记已读请求"""
    notification_ids: list[int] = Field(
        min_length=1,
        max_length=100,
        description="通知 ID 列表，单次最多 100 条",
    )


class WSNotificationPayload(BaseModel):
    """WebSocket 推送的实时通知载荷"""
    type: str                        # steal / friend_request / crop_mature / system / achievement
    title: str
    message: str
    from_user_id: int | None = None
    from_username: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class WSMessageEnvelope(BaseModel):
    """WebSocket 消息信封（统一所有 WS 消息格式）"""
    event: str                       # notification / heartbeat / ack
    payload: WSNotificationPayload | dict[str, Any]
    seq: int = 0                     # 消息序列号
```

---

## 5. 通知类型枚举

| type | 说明 | from_user 来源 |
|------|------|---------------|
| `steal` | 有人偷了你的作物 | 偷菜者 |
| `friend_request` | 收到好友请求 | 申请方 |
| `crop_mature` | 作物成熟了 | — (系统) |
| `system` | 系统通知 | — (系统) |
| `achievement` | 成就解锁 | — (系统) |

---

## 6. 与 routes/notification.md 集成说明

```python
# routes/notification.py

@router.get("/", response_model=NotificationListResponse)
async def get_notifications(
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(get_current_user),
    svc: NotificationService = Depends(get_notification_service),
):
    ...

@router.get("/unread/count", response_model=NotificationCountResponse)
async def get_unread_count(
    user: User = Depends(get_current_user),
    svc: NotificationService = Depends(get_notification_service),
):
    ...

@router.put("/read", response_model=NotificationCountResponse)
async def mark_as_read(
    payload: MarkReadRequest,
    user: User = Depends(get_current_user),
    svc: NotificationService = Depends(get_notification_service),
):
    ...
```

---

## 7. WebSocket 消息流转

```
事件触发 (steal/harvest/etc)
    │
    ▼
NotificationService.create()
    │
    ├──→ 写入 notifications 表（持久化）
    │
    └──→ WSManager.broadcast(user_id, WSNotificationPayload)
              │
              ▼
         客户端收到 → 更新角标 → 提示用户
```

WS 消息使用 `WSMessageEnvelope` 信封格式，`event` 字段区分消息类型（`notification`/`heartbeat`/`ack`）。
