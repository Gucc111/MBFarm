# 成就系统数据模型

## 模块职责

`app/models/achievement.py` 定义成就系统的两个核心数据模型：

- **`Achievement`**: 全局成就定义（类似种子常量），预置到数据库中
- **`UserAchievement`**: 每个用户每个成就的进度追踪

## 设计决策

### 事件驱动 vs 轮询

**选用事件驱动**。在 player 执行 plant / harvest / steal / login 等操作后，直接调用 `check_achievements(user_id, trigger_type, increment)` 检查相关成就进度，避免后台定时任务。

### 成就预置方案

所有 `Achievement` 记录在应用启动时由 Alembic seed 脚本预置（例如"新手入门"：种植 1 次，奖励 50 coins）。不允许多用户自定义成就。

### 奖励发放时机

当 `UserAchievement.completed` 从 `False` 变为 `True` 时，在 `check_achievements()` 的同一事务中发放奖励（更新 `users.coins` / `inventory` / `users.xp`）。`unlocked_at` 同时记录。

## SQL DDL

```sql
CREATE TABLE achievements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       VARCHAR(64)    NOT NULL,
    description VARCHAR(256)   NOT NULL,
    icon        VARCHAR(32)    NOT NULL DEFAULT '🏆',
    trigger_type VARCHAR(32)   NOT NULL,  -- plant / harvest / steal / login / xp_level / coins_total
    condition_value INTEGER     NOT NULL DEFAULT 1,
    reward_type VARCHAR(16)    NOT NULL,  -- coins / item / xp
    reward_value INTEGER        NOT NULL DEFAULT 0,
    created_at  DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_achievements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    achievement_id  INTEGER       NOT NULL REFERENCES achievements(id) ON DELETE CASCADE,
    progress        INTEGER       NOT NULL DEFAULT 0,
    completed       BOOLEAN       NOT NULL DEFAULT 0,
    unlocked_at     DATETIME      NULL,
    updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, achievement_id)
);
```

## 字段说明

### achievements

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, AUTOINCREMENT | 自增主键 |
| title | VARCHAR(64) | NOT NULL | 成就标题 |
| description | VARCHAR(256) | NOT NULL | 成就描述 |
| icon | VARCHAR(32) | NOT NULL, 默认 '🏆' | 图标标识（emoji） |
| trigger_type | VARCHAR(32) | NOT NULL | 触发类型：plant / harvest / steal / login / xp_level / coins_total |
| condition_value | Integer | NOT NULL, 默认 1 | 达成条件值 |
| reward_type | VARCHAR(16) | NOT NULL | 奖励类型：coins / item / xp |
| reward_value | Integer | NOT NULL, 默认 0 | 奖励数值 |
| created_at | DateTime | NOT NULL | 记录创建时间 |

### user_achievements

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, AUTOINCREMENT | 自增主键 |
| user_id | Integer | FK → users.id, ON DELETE CASCADE, NOT NULL | 所属用户 |
| achievement_id | Integer | FK → achievements.id, ON DELETE CASCADE, NOT NULL | 所属成就 |
| progress | Integer | NOT NULL, 默认 0 | 当前进度 |
| completed | Boolean | NOT NULL, 默认 0 | 是否已完成 |
| unlocked_at | DateTime | NULL | 首次解锁时间 |
| updated_at | DateTime | NOT NULL | 最后更新时间 |

## 关系说明

```
Achievement (1) ─── (N) UserAchievement ─── (1) User
```

- 一个成就定义可被多个用户完成
- 每个用户在每个成就上只有一条记录（UNIQUE 约束）
- 用户删除时级联清除其所有成就记录

## Python 实现

```python
"""app/models/achievement.py"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(256), nullable=False)
    icon: Mapped[str] = mapped_column(String(32), nullable=False, default="🏆")
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    condition_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reward_type: Mapped[str] = mapped_column(String(16), nullable=False)
    reward_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # 反向关系：用户完成记录
    user_achievements: Mapped[list["UserAchievement"]] = relationship(
        back_populates="achievement", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Achievement(id={self.id}, title='{self.title}')>"


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    achievement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # 反向关系
    achievement: Mapped["Achievement"] = relationship(back_populates="user_achievements")

    __table_args__ = (
        # 同一用户 + 同一成就只有一条记录
        {"sqlite_unique_constraints": ("UNIQUE(user_id, achievement_id)",)},
    )

    def __repr__(self) -> str:
        return (
            f"<UserAchievement(user_id={self.user_id}, "
            f"achievement_id={self.achievement_id}, "
            f"completed={self.completed})>"
        )
```

## 使用示例

```python
# --- 1. 预置成就（Alembic seed 脚本） ---
preseed_achievements = [
    Achievement(
        title="初次种植",
        description="完成第一次种植",
        icon="🌱",
        trigger_type="plant",
        condition_value=1,
        reward_type="coins",
        reward_value=50,
        created_at=datetime.utcnow(),
    ),
    Achievement(
        title="收获满满",
        description="累计收获 50 次作物",
        icon="🌾",
        trigger_type="harvest",
        condition_value=50,
        reward_type="coins",
        reward_value=200,
        created_at=datetime.utcnow(),
    ),
    Achievement(
        title="登门拜访",
        description="连续登录 7 天",
        icon="📅",
        trigger_type="login",
        condition_value=7,
        reward_type="xp",
        reward_value=30,
        created_at=datetime.utcnow(),
    ),
]

# --- 2. 事件驱动检查（在 plant 操作中调用） ---
async def check_achievements(
    db: AsyncSession,
    user_id: int,
    trigger_type: str,
    increment: int = 1,
) -> list[Achievement]:
    """检查并更新指定 trigger_type 的成就进度，返回已解锁的成就列表。"""
    unlocked: list[Achievement] = []

    targets = (
        await db.execute(
            select(UserAchievement)
            .join(Achievement)
            .where(
                UserAchievement.user_id == user_id,
                Achievement.trigger_type == trigger_type,
                UserAchievement.completed == False,  # noqa: E712
            )
        )
    ).scalars().all()

    for ua in targets:
        ua.progress += increment
        ua.updated_at = datetime.utcnow()

        if ua.progress >= ua.achievement.condition_value and not ua.completed:
            ua.completed = True
            ua.unlocked_at = datetime.utcnow()
            unlocked.append(ua.achievement)

    await db.flush()
    return unlocked


# --- 3. 查询用户所有成就进度 ---
async def get_user_achievements(db: AsyncSession, user_id: int) -> list[dict]:
    """获取用户所有成就的进度汇总。"""
    results = (
        await db.execute(
            select(Achievement, UserAchievement)
            .join(UserAchievement)
            .where(UserAchievement.user_id == user_id)
            .order_by(UserAchievement.completed.desc(), Achievement.title)
        )
    ).all()

    return [
        {
            "achievement": {
                "id": a.id,
                "title": a.title,
                "description": a.description,
                "icon": a.icon,
                "trigger_type": a.trigger_type,
                "condition_value": a.condition_value,
                "reward_type": a.reward_type,
                "reward_value": a.reward_value,
            },
            "progress": ua.progress,
            "completed": ua.completed,
            "unlocked_at": ua.unlocked_at,
        }
        for a, ua in results
    ]
```

## 预置成就建议清单

| 标题 | Trigger | Condition | Reward |
|------|---------|-----------|--------|
| 初次种植 | plant | 1 | 50 coins |
| 种植达人 | plant | 100 | 500 coins |
| 第一次收获 | harvest | 1 | 30 coins |
| 收获满满 | harvest | 50 | 200 coins |
| 丰收在望 | harvest | 200 | 800 coins |
| 偷菜高手 | steal | 20 | 100 coins |
| 被偷了！ | steal | 1 (作为被偷方) | 10 xp |
| 七日登录 | login | 7 | 30 xp |
| 连续登录王 | login | 30 | 200 coins |
| 小富翁 | coins_total | 1000 | 图标 🌟 |
| 大富翁 | coins_total | 10000 | 图标 👑 |
