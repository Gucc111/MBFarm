# 通知服务 (NotificationService)

## 模块职责

`app/services/notification_service.py` 实现通知系统的业务逻辑：

- 创建各种类型的通知（偷菜、作物成熟、好友请求、成就、系统）
- 查询通知列表（支持未读过滤、分页）
- 标记通知为已读（单条/批量）
- 统计未读数量
- 清理过期通知（定时任务）
- 通过 WebSocket 推送新通知

## 依赖注入

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db


async def get_notification_service(
    db: AsyncSession = Depends(get_db),
) -> "NotificationService":
    return NotificationService(db)
```

## 通知类型常量

```python
NOTIFICATION_TYPES = {
    "steal": {"label": "偷菜通知", "icon": "🥷"},
    "harvest_reminder": {"label": "作物成熟", "icon": "🌾"},
    "friend_request": {"label": "好友请求", "icon": "🤝"},
    "achievement": {"label": "成就解锁", "icon": "🏆"},
    "system": {"label": "系统通知", "icon": "📢"},
}
```

## NotificationService 完整代码

```python
"""app/services/notification_service.py"""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.core.websocket_manager import websocket_manager


class NotificationService:
    """通知系统业务逻辑"""

    def __init__(self, db: AsyncSession, ws_manager=None):
        self.db = db
        self.ws = ws_manager or websocket_manager

    async def create_notification(
        self,
        user_id: int,
        type: str,
        title: str,
        message: str,
        from_user_id: int | None = None,
    ) -> Notification:
        """创建通知并推送"""
        if type not in NOTIFICATION_TYPES:
            raise ValueError(f"不支持的通知类型: {type}")

        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            from_user_id=from_user_id,
            is_read=False,
            created_at=datetime.utcnow(),
        )
        self.db.add(notification)
        await self.db.flush()

        # 通过 WebSocket 推送
        if self.ws:
            try:
                await self.ws.send(user_id, {
                    "event": "notification.new",
                    "data": {
                        "id": notification.id,
                        "type": notification.type,
                        "title": notification.title,
                        "message": notification.message,
                        "from_user_id": notification.from_user_id,
                        "created_at": notification.created_at.isoformat(),
                    },
                })
            except Exception:
                # WebSocket 推送失败不影响通知创建
                pass

        return notification

    async def get_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        page: int = 1,
        per_page: int = 20,
    ) -> dict:
        """获取用户的通知列表"""
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.is_read == False)  # noqa: E712

        # 总数
        count_stmt = select(func.count(Notification.id)).where(
            Notification.user_id == user_id
        )
        if unread_only:
            count_stmt = count_stmt.where(Notification.is_read == False)  # noqa: E712
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # 分页
        offset = (page - 1) * per_page
        items_stmt = query.order_by(
            Notification.created_at.desc()
        ).offset(offset).limit(per_page)
        items = (await self.db.execute(items_stmt)).scalars().all()

        # 未读总数（用于前端角标）
        unread_count = (
            await self.db.execute(
                select(func.count(Notification.id)).where(
                    Notification.user_id == user_id,
                    Notification.is_read == False,  # noqa: E712
                )
            )
        ).scalar() or 0

        return {
            "notifications": [
                {
                    "id": n.id,
                    "type": n.type,
                    "title": n.title,
                    "message": n.message,
                    "from_user_id": n.from_user_id,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat(),
                }
                for n in items
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
            "unread_count": unread_count,
        }

    async def mark_as_read(self, notification_id: int, user_id: int) -> dict:
        """标记单条通知为已读"""
        notification = (
            await self.db.execute(
                select(Notification).where(
                    Notification.id == notification_id,
                    Notification.user_id == user_id,
                )
            )
        ).first()
        if not notification:
            raise ValueError("通知不存在或不属于当前用户")

        notification.is_read = True
        await self.db.flush()

        return {"message": "已标记为已读"}

    async def mark_all_as_read(self, user_id: int) -> dict:
        """批量标记所有未读通知为已读"""
        from sqlalchemy import update

        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .values(is_read=True)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()

        return {"marked_read": result.rowcount}

    async def get_unread_count(self, user_id: int) -> int:
        """获取用户未读通知数量"""
        result = (
            await self.db.execute(
                select(func.count(Notification.id)).where(
                    Notification.user_id == user_id,
                    Notification.is_read == False,  # noqa: E712
                )
            )
        ).scalar()
        return result or 0

    async def cleanup_old_notifications(self, days: int = 30) -> int:
        """清理过期已读通知（定时任务调用）"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        from sqlalchemy import delete

        stmt = (
            delete(Notification)
            .where(
                Notification.is_read == True,  # noqa: E712
                Notification.created_at < cutoff,
            )
        )
        result = await self.db.execute(stmt)
        await self.db.flush()

        return result.rowcount
```

## 各通知类型调用示例

### 偷菜通知

```python
# 在 steal_service.py 的 steal_crops 方法中
await notification_service.create_notification(
    user_id=victim_id,
    type="steal",
    title="作物被偷",
    message=f"你种了 {count} 株 {crop_name} 被 {thief_username} 偷了",
    from_user_id=thief_id,
)
```

### 作物成熟提醒

```python
# 在 harvest_service.py 的 harvest 方法中
await notification_service.create_notification(
    user_id=farmer_id,
    type="harvest_reminder",
    title="作物成熟了",
    message=f"你的 {crop_name} 已经成熟，可以收获了！",
)
```

### 好友请求通知

```python
# 在 friend_service.py 的 send_request 方法中
await notification_service.create_notification(
    user_id=to_user_id,
    type="friend_request",
    title="好友请求",
    message=f"{from_username} 请求添加你为好友",
    from_user_id=from_user_id,
)
```

### 成就解锁通知

```python
# 在 achievement_service.py 的 check_achievements 方法中
for achievement in unlocked_achievements:
    await notification_service.create_notification(
        user_id=user_id,
        type="achievement",
        title=f"解锁成就: {achievement.title}",
        message=achievement.description,
    )
```

### 系统通知

```python
# 在 admin 操作中发送系统公告
await notification_service.create_notification(
    user_id=all_user_ids,  # 批量调用或遍历
    type="system",
    title="系统维护通知",
    message="系统将于今晚 22:00 - 23:00 进行维护",
)
```

## WebSocket 推送机制

```
┌──────────┐     create_notification     ┌─────────────┐
│  Service  │ ────────────────────────→   │  Notification │
│          │                              │  (DB 写入)    │
│          │        flush()               └──────┬──────┘
│          │         │                          │
│          │         │          ws.send()       │
│          │         └──────────────────────────┘
│          │                          ↓
│          │                   ┌─────────────┐
│          │                   │ WebSocket   │
│          │                   │ Manager     │
│          │                   └──────┬──────┘
│          │                          │
│          │                   推送给目标用户
└──────────┘
```

## 使用示例

```python
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("")
async def list_notifications(
    service: NotificationService = Depends(get_notification_service),
    current_user_id: int = Depends(get_current_user_id),
    unread_only: bool = False,
    page: int = 1,
    per_page: int = 20,
):
    return await service.get_notifications(
        current_user_id, unread_only, page, per_page
    )

@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    service: NotificationService = Depends(get_notification_service),
    current_user_id: int = Depends(get_current_user_id),
):
    return await service.mark_as_read(notification_id, current_user_id)

@router.post("/mark-all-read")
async def mark_all_read(
    service: NotificationService = Depends(get_notification_service),
    current_user_id: int = Depends(get_current_user_id),
):
    return await service.mark_all_as_read(current_user_id)

@router.get("/types")
async def list_notification_types():
    return {"types": [
        {"type": k, "label": v["label"], "icon": v["icon"]}
        for k, v in NOTIFICATION_TYPES.items()
    ]}
```
