# 通知系统数据模型

## 模块职责

`app/models/notification.py` 定义通知系统的核心数据模型：

- **`Notification`**: 用户收到的通知记录，涵盖偷菜、作物成熟提醒、好友请求、成就解锁、系统公告等场景

## 设计决策

### 异步写入

通知写入是**非阻塞的**。在 steal / harvest / achievement_unlock 等操作完成之后，通过事件总线或简单的 `await db.execute(...)` 异步写入通知，不阻塞主操作的事务提交。

### 通知轮转清理

已读通知保留 **30 天**后由定时任务（如每天凌晨 2 点的 cron job）自动删除，控制表规模。未读通知不清理，由用户手动阅读或批量已读。

### 实时推送时机

当通知写入成功后，通过已有的 WebSocket 连接推送 `notification.new` 事件给对应用户，浏览器收到后显示桌面通知或角标数字。

## SQL DDL

```sql
CREATE TABLE notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type        VARCHAR(32)   NOT NULL,          -- steal / harvest_reminder / friend_request / system / achievement
    title       VARCHAR(64)   NOT NULL,
    message     VARCHAR(256)  NOT NULL,
    from_user_id INTEGER      NULL REFERENCES users(id),
    is_read     BOOLEAN       NOT NULL DEFAULT 0,
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notifications_user_read ON notifications(user_id, is_read);
CREATE INDEX idx_notifications_user_time ON notifications(user_id, created_at DESC);
```

## 字段说明

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, AUTOINCREMENT | 自增主键 |
| user_id | Integer | FK → users.id, ON DELETE CASCADE, NOT NULL | 通知接收者 |
| type | VARCHAR(32) | NOT NULL | 通知类型 |
| title | VARCHAR(64) | NOT NULL | 通知标题 |
| message | VARCHAR(256) | NOT NULL | 通知内容 |
| from_user_id | Integer | FK → users.id, nullable | 发起者（偷菜的人、好友请求发送者等） |
| is_read | Boolean | NOT NULL, 默认 False | 是否已读 |
| created_at | DateTime | NOT NULL | 创建时间 |

### type 枚举值

| 类型 | 触发场景 |
|------|----------|
| `steal` | 他人偷了你的作物 |
| `harvest_reminder` | 你的作物已成熟，可以收获 |
| `friend_request` | 收到好友请求 |
| `system` | 系统公告 / 维护通知 |
| `achievement` | 解锁了新成就 |

## 关系说明

```
Notification (N) ─── (1) User (user_id)
Notification (N) ─── (1) User (from_user_id, nullable)
```

- 每条通知指向一个接收者（必须存在）
- `from_user_id` 为可选字段，`system` 类型通知不需要发起者

## Python 实现

```python
"""app/models/notification.py"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(String(256), nullable=False)
    from_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # 反向关系：接收者
    recipient: Mapped["User"] = relationship(
        foreign_keys="Notification.user_id", back_populates="notifications"
    )
    # 反向关系：发起者（可选）
    sender: Mapped["User"] = relationship(
        foreign_keys="Notification.from_user_id", back_populates="sent_notifications"
    )

    __table_args__ = (
        Index("idx_notifications_user_read", "user_id", "is_read"),
        Index("idx_notifications_user_time", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id}, user_id={self.user_id}, "
            f"type='{self.type}', is_read={self.is_read})>"
        )
```

## 使用示例

```python
from datetime import datetime, timedelta
from sqlalchemy import select

# --- 1. 创建通知（在 steal 操作完成后调用） ---
async def notify_steal(
    db: AsyncSession,
    victim_id: int,
    thief_id: int,
    crop_name: str,
    steal_count: int,
) -> None:
    """通知：你的作物被偷了"""
    notification = Notification(
        user_id=victim_id,
        type="steal",
        title="作物被偷",
        message=f"你种了 {steal_count} 株 {crop_name} 被偷了",
        from_user_id=thief_id,
        created_at=datetime.utcnow(),
    )
    db.add(notification)
    await db.flush()

    # 通过 WebSocket 推送（异步，不阻塞）
    # await websocket_manager.send(victim_id, {
    #     "event": "notification.new",
    #     "data": notification.to_dict(),
    # })


# --- 2. 查询未读通知 ---
async def get_unread_notifications(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """分页查询用户未读通知"""
    offset = (page - 1) * per_page

    count_stmt = (
        select(db.func.count(Notification.id))
        .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    items_stmt = (
        select(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    items = (await db.execute(items_stmt)).scalars().all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [n.__dict__ for n in items],  # 实际应使用 Pydantic Schema
    }


# --- 3. 批量标记已读 ---
async def mark_all_as_read(
    db: AsyncSession,
    user_id: int,
) -> int:
    """批量标记用户所有未读通知为已读，返回影响行数"""
    stmt = (
        Notification.__table__
        .update()
        .where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True, created_at=datetime.utcnow())
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount


# --- 4. 清理过期已读通知（定时任务调用） ---
async def cleanup_old_notifications(
    db: AsyncSession,
    days: int = 30,
) -> int:
    """删除超过指定天数的已读通知，返回删除数量"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    stmt = (
        Notification.__table__
        .delete()
        .where(
            Notification.is_read == True,  # noqa: E712
            Notification.created_at < cutoff,
        )
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount
```

## 通知创建时机清单

| 事件 | 通知类型 | 接收者 | 发起者 |
|------|----------|--------|--------|
| A 偷了 B 的作物 | `steal` | B | A |
| 作物成熟 | `harvest_reminder` | 农场主人 | — |
| 收到好友请求 | `friend_request` | 被请求方 | 请求方 |
| 解锁成就 | `achievement` | 用户 | — |
| 系统维护公告 | `system` | 所有在线用户 | 系统 |
