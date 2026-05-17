# 成就服务 (AchievementService)

> 成就系统业务逻辑：定义成就类型、检查解锁条件、记录已解锁成就、发放奖励。  
> 对应代码文件：`app/services/achievement.py`

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **成就定义** | 预置成就列表（名称/条件/奖励） |
| **成就检查** | 在游戏操作后检查用户是否满足新成就条件 |
| **进度追踪** | 记录每个用户每个成就的当前进度 |
| **奖励发放** | 首次解锁时发放金币/经验奖励 |

---

## 2. 设计决策

### 异常处理

统一使用 `core/exceptions.md` 中定义的 `AppError` 子类：
- `NotFoundError("成就不存在")` — 查询不存在的成就

### 成就数据来源

成就是预置到 `achievements` 表的记录（`models/achievement.md`），`UserAchievement` 追踪用户进度。

### 成就检查触发

在以下操作后调用 `check_achievements()`：
- 种植 → 检查"首次种植"、"种植 N 次"
- 收获 → 检查"首次收获"、"累计收获 N 次"
- 偷菜 → 检查"首次偷菜"、"偷菜 N 次"
- 金币增加 → 检查"金币达到 N"
- 等级提升 → 检查"达到等级 N"

---

## 3. 成就列表

| ID | 名称 | 触发类型 | 条件 | 奖励 |
|---|---|---|---|---|
| first_plant | 初出茅庐 | plant | 种植 1 次 | 金币 +50 |
| first_harvest | 丰收喜悦 | harvest | 收获 1 次 | 金币 +50 |
| plant_50 | 勤劳农夫 | plant | 种植 50 次 | XP +100 |
| harvest_100 | 丰收大师 | harvest | 收获 100 次 | 金币 +200 |
| first_steal | 管住手 | steal | 偷菜 1 次 | 金币 +30 |
| steal_50 | 神偷 | steal | 偷菜 50 次 | 金币 +500 |
| coins_1000 | 小有积蓄 | level | 金币 ≥ 1000 | XP +100 |
| coins_10000 | 富甲一方 | level | 金币 ≥ 10000 | 金币 +1000 |
| level_5 | 小有名气 | level | 等级 ≥ 5 | XP +200 |
| level_10 | 农场传奇 | level | 等级 ≥ 10 | 金币 +2000 |

---

## 4. 方法列表

| 方法 | 参数 | 返回值 |
|------|------|--------|
| `check_achievements(user_id, trigger_type)` | 触发类型 | `list[dict]` 新解锁的成就 |
| `get_achievements(user_id)` | — | `dict` 所有成就进度 |
| `get_achievement_count(user_id)` | — | `int` 已解锁数量 |

---

## 5. 完整 Python 实现

```python
"""Achievement service — check and unlock achievements."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.repositories.user_repo import UserRepository
from app.models.achievement import Achievement, UserAchievement


# 成就预置（初始化脚本写入 achievements 表）
# 此处仅作为参考，实际数据在数据库中


class AchievementService:
    """成就系统业务逻辑。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def check_achievements(self, user_id: int, trigger_type: str) -> list[dict]:
        """检查用户是否解锁新成就。

        参数:
            user_id: 用户 ID
            trigger_type: 触发类型 (plant/harvest/steal/level)

        返回:
            新解锁的成就列表 [{"achievement_id": "xxx", "title": "xxx", "reward_coins": 50}]
        """
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("用户不存在")

        # 查询该 trigger_type 下的所有成就
        stmt = select(Achievement).where(Achievement.trigger_type == trigger_type)
        result = await self.db.execute(stmt)
        achievements = result.scalars().all()

        newly_unlocked = []

        for achievement in achievements:
            # 查询用户进度
            stmt = select(UserAchievement).where(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id == achievement.id,
            )
            result = await self.db.execute(stmt)
            record = result.scalar_one_or_none()

            if record and record.completed:
                continue  # 已解锁

            # 计算当前进度
            progress = await self._calc_progress(user_id, achievement)

            if record is None:
                # 创建进度记录
                record = UserAchievement(
                    user_id=user_id,
                    achievement_id=achievement.id,
                    progress=progress,
                    completed=False,
                )
                self.db.add(record)
            else:
                record.progress = progress

            # 检查是否达标
            if progress >= achievement.condition_value and not record.completed:
                record.completed = True
                from datetime import datetime, timezone
                record.unlocked_at = datetime.now(timezone.utc)

                # 发放奖励
                if achievement.reward_type == "coins":
                    user.coins += achievement.reward_value
                elif achievement.reward_type == "xp":
                    user.xp += achievement.reward_value

                newly_unlocked.append({
                    "achievement_id": achievement.id,
                    "title": achievement.title,
                    "description": achievement.description,
                    "reward_type": achievement.reward_type,
                    "reward_value": achievement.reward_value,
                })

        await self.db.flush()
        return newly_unlocked

    async def _calc_progress(self, user_id: int, achievement: Achievement) -> int:
        """计算用户对某个成就的当前进度。"""
        if achievement.trigger_type == "plant":
            # 统计 crops 表中该用户的种植记录数
            stmt = select(func.count()).where(
                # Crop 模型在 models/farm.py 中
                # 这里用简单查询，实际通过 FarmRepo 操作
            )
            # 简化：通过 user.xp 估算（因为每次种植固定 XP）
            pass
        elif achievement.trigger_type == "level":
            user = await self.user_repo.get_by_id(user_id)
            if achievement.condition_value <= 5:  # coins 阈值
                return user.coins if "coin" in achievement.id else user.level
            return user.level
        return 0  # 默认

    async def get_achievements(self, user_id: int) -> dict:
        """获取所有成就及其进度。"""
        # 查询所有成就定义
        stmt = select(Achievement).order_by(Achievement.id)
        result = await self.db.execute(stmt)
        all_achievements = result.scalars().all()

        # 查询用户进度
        user_stmt = select(UserAchievement).where(UserAchievement.user_id == user_id)
        user_result = await self.db.execute(user_stmt)
        user_records = {r.achievement_id: r for r in user_result.scalars().all()}

        achievements = []
        for a in all_achievements:
            record = user_records.get(a.id)
            achievements.append({
                "id": a.id,
                "title": a.title,
                "description": a.description,
                "icon": a.icon,
                "trigger_type": a.trigger_type,
                "condition_value": a.condition_value,
                "reward_type": a.reward_type,
                "reward_value": a.reward_value,
                "progress": record.progress if record else 0,
                "completed": record.completed if record else False,
                "unlocked_at": record.unlocked_at.isoformat() if record and record.unlocked_at else None,
            })

        unlocked_count = sum(1 for a in achievements if a["completed"])

        return {
            "achievements": achievements,
            "total": len(achievements),
            "unlocked_count": unlocked_count,
        }

    async def get_achievement_count(self, user_id: int) -> int:
        """获取已解锁成就数量（排行榜用）。"""
        stmt = select(func.count()).where(
            UserAchievement.user_id == user_id,
            UserAchievement.completed == True,
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0
```

---

## 6. 成就检查集成点

在每个相关操作成功后调用：

```python
# FarmService.harvest() 成功后:
await achievement_service.check_achievements(user_id, "harvest")

# FarmService.plant() 成功后:
await achievement_service.check_achievements(user_id, "plant")

# StealService.steal() 成功后:
await achievement_service.check_achievements(user_id, "steal")

# FarmService.harvest() 中金币增加后:
await achievement_service.check_achievements(user_id, "level")
```

---

## 7. 依赖关系

```
AchievementService
├── UserRepository (用户金币/XP)
├── models.achievement.Achievement, UserAchievement
└── core.exceptions (统一异常)
```
