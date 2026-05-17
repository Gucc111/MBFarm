# Achievement Schemas (成就系统 Pydantic v2 校验模型)

## 模块职责

本模块定义成就系统相关的所有 Pydantic 数据验证模型，统一数据进出格式。

## Schema 列表

| Schema | 用途 |
|---|---|
| `AchievementResponse` | 成就定义（只读响应） |
| `UserAchievementProgress` | 用户某项成就的进度 |
| `AchievementListResponse` | 用户全部成就汇总 |
| `AchievementUnlockEvent` | WebSocket 推送的解锁事件 |

## 字段校验规则

| Schema | 字段 | 类型 | 约束 |
|---|---|---|---|
| AchievementResponse | id | int | 主键 |
| | title | str | max 64 |
| | description | str | max 256 |
| | icon | str | max 32, 默认 `🏅` |
| | trigger_type | str | 枚举: `plant`, `harvest`, `steal`, `water`, `level_up` |
| | condition_value | int | ≥ 1 |
| | reward_type | str | 枚举: `coins`, `xp`, `item` |
| | reward_value | int | ≥ 0 |
| UserAchievementProgress | progress | int | ≥ 0 |
| | completed | bool | 派生: progress ≥ condition_value |
| | unlocked_at | datetime \| None | 解锁时间 |
| AchievementListResponse | total | int | 派生: len(achievements) |
| | unlocked_count | int | 派生: completed 数量 |
| AchievementUnlockEvent | user_id | int | ≥ 1 |
| | username | str | max 32 |
| | achievement_title | str | max 64 |

## 完整 Python 代码

```python
"""app/schemas/achievement.py — 成就系统 Pydantic v2 校验模型."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, computed_field


# ── 枚举 ──────────────────────────────────────────────────────────

class TriggerType(str, Enum):
    PLANT = "plant"
    HARVEST = "harvest"
    STEAL = "steal"
    WATER = "water"
    LEVEL_UP = "level_up"


class RewardType(str, Enum):
    COINS = "coins"
    XP = "xp"
    ITEM = "item"


# ── Schema ────────────────────────────────────────────────────────

class AchievementResponse(BaseModel):
    """成就定义（只读响应，from_attributes=True）."""

    id: int
    title: Annotated[str, Field(max_length=64)]
    description: Annotated[str, Field(max_length=256)]
    icon: Annotated[str, Field(default="🏅", max_length=32)]
    trigger_type: TriggerType
    condition_value: Annotated[int, Field(ge=1)]
    reward_type: RewardType
    reward_value: Annotated[int, Field(ge=0)]

    model_config = {"from_attributes": True}


class UserAchievementProgress(BaseModel):
    """用户某项成就的进度."""

    achievement: AchievementResponse
    progress: Annotated[int, Field(ge=0)]
    unlocked_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def completed(self) -> bool:
        """progress ≥ condition_value 即为已完成."""
        return self.progress >= self.achievement.condition_value

    model_config = {"from_attributes": True}


class AchievementListResponse(BaseModel):
    """用户全部成就汇总."""

    achievements: list[UserAchievementProgress]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        return len(self.achievements)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def unlocked_count(self) -> int:
        return sum(1 for a in self.achievements if a.completed)

    model_config = {"from_attributes": True}


class AchievementUnlockEvent(BaseModel):
    """WebSocket 推送的成就解锁事件."""

    user_id: Annotated[int, Field(ge=1)]
    username: Annotated[str, Field(max_length=32)]
    achievement_title: Annotated[str, Field(max_length=64)]
    unlocked_at: datetime

    model_config = {"from_attributes": True}
```

## 与 routes/achievement.md 集成说明

- `GET /api/achievements` → 返回 `AchievementListResponse`
- WebSocket `achievement_unlock` 事件 → 推送 `AchievementUnlockEvent`
- `AchievementResponse` 被 `UserAchievementProgress` 嵌套引用，无需单独端点。
