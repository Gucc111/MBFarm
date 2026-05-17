# Schema: Leaderboard

## 模块职责

排行榜 Pydantic v2 校验模型，用于排行榜查询和返回的用户数据验证。

---

## Schema 列表

| Schema | 用途 | 关键字段 |
|---|---|---|
| `LeaderboardType` | 排行榜类型枚举 | wealth, crop_count, steal_count, achievement_count |
| `LeaderboardEntry` | 排行榜条目 | rank, user_id, username, score, label |
| `LeaderboardResponse` | 排行榜列表响应 | type, entries, total, page, per_page |
| `UserRankResponse` | 单个用户排名响应 | user_id, username, rank, score, total_players |

---

## 字段校验规则

| Schema | 字段 | 规则 |
|---|---|---|
| `LeaderboardEntry` | `rank` | 正整数 |
| `LeaderboardEntry` | `score` | 非负整数 |
| `LeaderboardResponse` | `page` | 正整数 |
| `LeaderboardResponse` | `per_page` | 正整数, 默认 10 |
| `UserRankResponse` | `total_players` | 正整数 |

---

## 完整 Python 代码

```python
"""app/schemas/leaderboard.py — Leaderboard Pydantic v2 schemas."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, ConfigDict


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------

class LeaderboardType(str, Enum):
    """排行榜类型。"""
    WEALTH = "wealth"                              # 按总资产排名
    CROP_COUNT = "crop_count"                      # 按总收获数排名
    STEAL_COUNT = "steal_count"                    # 按偷菜次数排名
    ACHIEVEMENT_COUNT = "achievement_count"        # 按成就数量排名


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class LeaderboardEntry(BaseModel):
    """排行榜单条记录。"""
    model_config = ConfigDict(from_attributes=True)

    rank: Annotated[int, Field(gt=0)]             # 排名，从 1 开始
    user_id: int
    username: str
    score: Annotated[int, Field(ge=0)]            # 对应的数值（分数）
    label: Annotated[str, Field(max_length=128)]  # 显示说明，如 "¥12,345"

    def __hash__(self) -> int:
        return hash(self.user_id)


class LeaderboardResponse(BaseModel):
    """排行榜分页列表响应。"""
    model_config = ConfigDict(from_attributes=True)

    type: LeaderboardType
    entries: Annotated[list[LeaderboardEntry], Field(min_length=1, max_length=100)]
    total: Annotated[int, Field(ge=0)]            # 参与排名总人数
    page: Annotated[int, Field(gt=0)]             # 当前页码
    per_page: Annotated[int, Field(gt=0, default=10)]


class UserRankResponse(BaseModel):
    """当前用户在指定排行榜中的排名。"""
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    rank: Annotated[int, Field(gt=0)]             # 用户排名
    score: Annotated[int, Field(ge=0)]
    total_players: Annotated[int, Field(ge=1)]    # 参与排名总人数
```

---

## 与 `routes/leaderboard.md` 集成

```python
# app/routes/leaderboard.py 中的导入示例
from app.schemas.leaderboard import (
    LeaderboardType,
    LeaderboardEntry,
    LeaderboardResponse,
    UserRankResponse,
)

@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    summary="全局排行榜",
)
def get_leaderboard(
    lb_type: LeaderboardType = Query(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
):
    ...

@router.get(
    "/leaderboard/me",
    response_model=UserRankResponse,
    summary="我的排名",
)
def get_my_rank(
    lb_type: LeaderboardType = Query(...),
    current_user_id: int = Depends(get_current_user),
):
    ...
```

---

*文档生成时间: 2025-07-10*
