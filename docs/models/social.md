# Social Module

## 模块职责

`app/models/social.py` — 定义社交关系模型，管理好友请求、好友关系和黑名单。

## 设计决策

### 1. 有向关系

Friendship 表存储有向边 A→B（A 是发起方，B 是接收方）。双向好友需要两条记录：

- `user_id=A, friend_id=B, status=accepted`（A 的好友列表包含 B）
- `user_id=B, friend_id=A, status=accepted`（B 的好友列表包含 A）

**理由**：好友请求是单向的，A 可以申请加 B，但 B 不一定同意。最终好友关系需要双方确认。

### 2. 状态机

| 状态      | 说明                                    |
|-----------|-----------------------------------------|
| pending   | 请求已发送，等待对方回应                  |
| accepted  | 双方已互为好友                            |
| rejected  | 对方拒绝了请求                            |
| blocked   | 拉黑，不允许对方加自己                    |

### 3. UNIQUE 约束

`UNIQUE(user_id, friend_id)` 确保同一对用户之间只有一条记录。如果需要重新发送请求，需要先删除旧记录。

## SQL DDL

```sql
CREATE TABLE friendships (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    friend_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status     TEXT(16)  NOT NULL CHECK(status IN ('pending', 'accepted', 'rejected', 'blocked')),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,

    UNIQUE(user_id, friend_id)
);

CREATE INDEX idx_friendships_user ON friendships(user_id);
CREATE INDEX idx_friendships_friend ON friendships(friend_id);
```

## 字段说明

| 字段      | 类型       | 约束                                    | 说明                                  |
|-----------|------------|-----------------------------------------|---------------------------------------|
| id        | BigInteger | PK, AUTOINCREMENT                       | 自增主键                              |
| user_id   | BigInteger | FK → users.id, NOT NULL, CASCADE, INDEX | 发起方用户                            |
| friend_id | BigInteger | FK → users.id, NOT NULL, CASCADE, INDEX | 目标用户                              |
| status    | Text(16)   | NOT NULL, CHECK enum, DEFAULT pending   | 关系状态                              |
| created_at| DateTime   | NOT NULL, DEFAULT UTC now()             | 请求创建时间                          |
| updated_at| DateTime   | NOT NULL, DEFAULT UTC now(), ON UPDATE  | 最后更新时间                          |

## 关系说明

- **User (user_id) → Friendship**：一对多（一个用户发起的众多请求）
- **User (friend_id) → Friendship**：一对多（一个用户收到的众多请求）
- **级联删除**：删除用户时，其发起和收到的所有好友请求自动清除
- **relationship**：`user` 和 `friend` 两个关系均使用 `lazy="selectin"`，无 `back_populates`（User 模型不维护反向引用）
- **自引用 FK**：user_id 和 friend_id 都指向 users 表

## Python 实现

```python
"""Social models — friend relationships and blocks."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class FriendshipStatus(StrEnum):
    """好友关系状态枚举。"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class Friendship(Base):
    """好友关系表 — 有向关系，双向好友需两条记录。"""

    __tablename__ = "friendships"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    friend_id = Column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(
        String(16),
        nullable=False,
        server_default=FriendshipStatus.PENDING,
    )
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships (lazy-loaded, used by selectinload in the repo)
    user = relationship("User", foreign_keys=[user_id], lazy="selectin")
    friend = relationship("User", foreign_keys=[friend_id], lazy="selectin")

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "friend_id", name="uix_user_friend"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'blocked')",
            name="chk_friendship_status",
        ),
    )

    def accept(self) -> None:
        self.status = FriendshipStatus.ACCEPTED
        self.updated_at = datetime.now(timezone.utc)

    def reject(self) -> None:
        self.status = FriendshipStatus.REJECTED
        self.updated_at = datetime.now(timezone.utc)

    def block(self) -> None:
        self.status = FriendshipStatus.BLOCKED
        self.updated_at = datetime.now(timezone.utc)

    @property
    def is_active(self) -> bool:
        return self.status in (FriendshipStatus.PENDING, FriendshipStatus.ACCEPTED)
```

> **注**：User 模型无需添加反向 relationship。Friendship 通过 `user` 和 `friend` 两个关系直接引用 User，仓库层通过 `selectinload(Friendship.user)` / `selectinload(Friendship.friend)` 预加载用户数据。

## 使用示例

```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.social import Friendship, FriendshipStatus
from sqlalchemy import select


async def send_friend_request(db: AsyncSession, user_id: int, friend_id: int) -> Friendship:
    """发送好友请求（需先检查是否存在已有记录）。"""
    result = await db.execute(
        select(Friendship).where(
            Friendship.user_id == user_id,
            Friendship.friend_id == friend_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.status == FriendshipStatus.BLOCKED:
            raise ValueError("Cannot send request to blocked user")
        if existing.status == FriendshipStatus.PENDING:
            raise ValueError("Friend request already pending")
        raise ValueError("Friend relationship already exists")

    friendship = Friendship(user_id=user_id, friend_id=friend_id)
    db.add(friendship)
    return friendship


async def accept_friend_request(db: AsyncSession, requester_id: int, acceptor_id: int) -> None:
    """接受好友请求，并创建双向关系。"""
    req = await db.execute(
        select(Friendship).where(
            Friendship.user_id == requester_id,
            Friendship.friend_id == acceptor_id,
            Friendship.status == FriendshipStatus.PENDING,
        )
    )
    req = req.scalar_one_or_none()
    if not req:
        raise ValueError("No pending request found")
    req.accept()

    reverse = Friendship(
        user_id=acceptor_id,
        friend_id=requester_id,
        status=FriendshipStatus.ACCEPTED,
    )
    db.add(reverse)


async def get_mutual_friends(db: AsyncSession, user_id: int) -> list:
    """获取互为好友的用户列表。"""
    from app.models.user import User

    result = await db.execute(
        select(User).join(
            Friendship, User.id == Friendship.friend_id
        ).where(
            Friendship.user_id == user_id,
            Friendship.status == FriendshipStatus.ACCEPTED,
        ).join(
            Friendship, Friendship.user_id == User.id
        ).where(
            Friendship.friend_id == user_id,
            Friendship.status == FriendshipStatus.ACCEPTED,
        )
    )
    return list(result.scalars().all())
```

## 扩展计划

| 阶段 | 扩展内容                            |
|------|-------------------------------------|
| P2   | 黑名单功能（blocked 状态实际使用）    |
| P2   | 访客记录（非好友也能来访）            |
| P3   | 社区/Guild 系统                      |
| P3   | 偷菜日志关联（谁偷了谁的菜）          |
