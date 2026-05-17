# Service: Leaderboard

## 模块职责

`LeaderboardService` 负责排行榜的核心业务逻辑：计算用户分数、获取排名列表、查询用户个人排名。

---

## 依赖

| 文件 | 依赖项 |
|---|---|
| `app/models/user.py` | `User` |
| `app/services/economy.py` | `EconomyService.get_gold(user_id)` |
| `app/services/crop.py` | `CropService.count_total_harvest(user_id)` |
| `app/services/steal.py` | `StealService.count_steals(user_id)` |
| `app/services/achievement.py` | `AchievementService.get_achievement_count(user_id)` |
| `app/schemas/leaderboard.py` | Leaderboard 相关 Pydantic schemas |

---

## `LeaderboardService` 类

```python
"""app/services/leaderboard.py — Leaderboard service."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.models.user import User
from app.schemas.leaderboard import (
    LeaderboardType,
    LeaderboardEntry,
    LeaderboardResponse,
    UserRankResponse,
)

logger = logging.getLogger(__name__)


class LeaderboardService:
    """排行榜服务。"""

    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def get_leaderboard(
        self,
        lb_type: LeaderboardType,
        page: int = 1,
        per_page: int = 10,
    ) -> LeaderboardResponse:
        """获取排行榜列表。"""
        # 获取所有用户的分数
        scores = await self._get_all_scores(lb_type)

        # 按分数降序排序
        sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)

        # 分页
        total = len(sorted_scores)
        start = (page - 1) * per_page
        end = start + per_page
        page_scores = sorted_scores[start:end]

        # 构建条目
        entries = [
            self._build_entry(user_id, username, score, lb_type)
            for i, (user_id, username, score) in enumerate(page_scores, start=start + 1)
        ]

        return LeaderboardResponse(
            type=lb_type,
            entries=entries,
            total=total,
            page=page,
            per_page=per_page,
        )

    async def get_user_rank(
        self,
        lb_type: LeaderboardType,
        user_id: int,
    ) -> UserRankResponse:
        """获取用户在排行榜中的排名。"""
        scores = await self._get_all_scores(lb_type)
        sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)

        user_rank = None
        for rank, (uid, username, score) in enumerate(sorted_scores, 1):
            if uid == user_id:
                user_rank = UserRankResponse(
                    user_id=uid,
                    username=username,
                    rank=rank,
                    score=score,
                    total_players=len(sorted_scores),
                )
                break

        if not user_rank:
            # 用户不在排行榜中（无数据）
            score = await self._compute_score(lb_type, user_id)
            rank = len(sorted_scores) + 1
            user = await self._get_user(user_id)
            username = user.username if user else f"user_{user_id}"
            user_rank = UserRankResponse(
                user_id=user_id,
                username=username,
                rank=rank,
                score=score,
                total_players=len(sorted_scores),
            )

        return user_rank

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    async def _get_all_scores(self, lb_type: LeaderboardType) -> list[tuple]:
        """获取所有用户的分数 (user_id, username, score)。"""
        query = select(User.id, User.username)
        result = await self.db.execute(query)
        users = result.all()

        scores = []
        for user_id, username in users:
            score = await self._compute_score(lb_type, user_id)
            scores.append((user_id, username, score))

        return scores

    async def _compute_score(
        self,
        lb_type: LeaderboardType,
        user_id: int,
    ) -> int:
        """根据排行类型计算分数。"""
        if lb_type == LeaderboardType.WEALTH:
            from app.services.economy import EconomyService
            service = EconomyService(self.db)
            return await service.get_gold(user_id)

        elif lb_type == LeaderboardType.CROP_COUNT:
            from app.services.crop import CropService
            service = CropService(self.db)
            return await service.count_total_harvest(user_id)

        elif lb_type == LeaderboardType.STEAL_COUNT:
            from app.services.steal import StealService
            service = StealService(self.db)
            return await service.count_steals(user_id)

        elif lb_type == LeaderboardType.ACHIEVEMENT_COUNT:
            from app.services.achievement import AchievementService
            service = AchievementService(self.db)
            return await service.get_achievement_count(user_id)

        else:
            raise ValueError(f"Unknown leaderboard type: {lb_type}")

    async def _get_user(self, user_id: int) -> Optional[User]:
        """获取用户对象。"""
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def _build_entry(
        self,
        user_id: int,
        username: str,
        score: int,
        lb_type: LeaderboardType,
    ) -> LeaderboardEntry:
        """构建排行榜条目。"""
        labels = {
            LeaderboardType.WEALTH: f"¥{score:,}",
            LeaderboardType.CROP_COUNT: f"🌾 {score}",
            LeaderboardType.STEAL_COUNT: f"🦊 {score}",
            LeaderboardType.ACHIEVEMENT_COUNT: f"🏆 {score}",
        }
        return LeaderboardEntry(
            rank=0,  # 会在调用方设置
            user_id=user_id,
            username=username,
            score=score,
            label=labels.get(lb_type, str(score)),
        )
```

---

## 排行类型计算逻辑

| 类型 | 数据来源 | 计算方式 |
|---|---|---|
| WEALTH | `UserWallet.gold` | 直接读取金币 |
| CROP_COUNT | `Crop` 表 | count(status='harvested') |
| STEAL_COUNT | `StolenCrop` 表 | count(stealer_id=user_id) |
| ACHIEVEMENT_COUNT | `AchievementRecord` 表 | count(status='unlocked') |

---

## 性能优化策略

1. **排行榜缓存**: 可使用 Redis 缓存排行榜数据，每 5 分钟刷新
2. **增量更新**: 每次操作后更新排行榜缓存而非全量计算
3. **异步预计算**: 在低峰期预计算排行榜

```python
# 缓存示例（伪代码）
import aiocache

cache = aiocache.SimpleMemoryCache(namespace="leaderboard")

async def get_leaderboard_cached(lb_type, page=1, per_page=10):
    cache_key = f"leaderboard:{lb_type}:{page}:{per_page}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = await self.get_leaderboard(lb_type, page, per_page)
    await cache.set(cache_key, result, ttl=300)  # 5 分钟
    return result
```

---

## 与 `routes/leaderboard.md` 集成

```python
# app/routes/leaderboard.py
from app.services.leaderboard import LeaderboardService

@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    lb_type: LeaderboardType = Query(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    service: LeaderboardService = Depends(LeaderboardService),
):
    return await service.get_leaderboard(lb_type, page, per_page)

@router.get("/leaderboard/me", response_model=UserRankResponse)
async def get_my_rank(
    lb_type: LeaderboardType = Query(...),
    current_user_id: int = Depends(get_current_user),
    service: LeaderboardService = Depends(LeaderboardService),
):
    return await service.get_user_rank(lb_type, current_user_id)
```

---

*文档生成时间: 2025-07-10*
