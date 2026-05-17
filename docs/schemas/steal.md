# 偷菜模块 Pydantic Schema

> 定义偷菜系统的 Pydantic v2 数据验证模型。  
> 对应代码文件：`app/schemas/steal.py`

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **偷菜请求校验** | 校验目标用户 ID |
| **偷菜结果响应** | 返回偷取的作物信息 |
| **偷菜记录列表** | 返回偷菜历史 |

---

## 2. Schema 列表

| 类名 | 用途 | 方向 |
|------|------|------|
| `StealRequest` | 偷菜请求体 | 请求 |
| `StealResult` | 偷菜结果 | 响应 |
| `StealRecord` | 偷菜记录（历史） | 响应 |
| `StealHistoryResponse` | 偷菜历史列表 | 响应 |

---

## 3. 字段校验规则

| Schema | 字段 | 类型 | 规则 |
|--------|------|------|------|
| `StealRequest` | `target_user_id` | int | `gt=0` |

---

## 4. 完整 Python 实现

```python
"""Steal module Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StealRequest(BaseModel):
    """偷菜请求体"""
    target_user_id: int = Field(gt=0, description="目标用户 ID")


class StealResult(BaseModel):
    """偷菜结果"""
    seed_type: str
    seed_name: str
    quantity: int
    value: int


class StealRecord(BaseModel):
    """偷菜记录（历史）"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    stealer_id: int | None = None
    victim_id: int | None = None
    stolen_crop_type: str
    quantity: int = 1
    stolen_at: str  # ISO format datetime


class StealHistoryResponse(BaseModel):
    """偷菜历史列表"""
    records: list[StealRecord]
    total: int
```

---

## 5. 与 routes/steal.md 集成

```python
from app.schemas.steal import StealResult, StealHistoryResponse

@router.post("/{target_user_id}", response_model=StealResult)
async def steal_crop(
    target_user_id: int,
    user: User = Depends(get_current_user),
    svc: StealService = Depends(_get_service),
):
    ...

@router.get("/my", response_model=StealHistoryResponse)
async def get_my_stolen(
    user: User = Depends(get_current_user),
    svc: StealService = Depends(_get_service),
):
    ...
```

---

## 6. 设计决策

### StealRecord 字段命名

`StealRecord.stolen_crop_type` 与 `StealLog.stolen_crop_type` 保持一致，而非使用 `seed_type`。这样在 `from_attributes=True` 模式下可以直接从 ORM 对象转换。

### StealResult 不标记 from_attributes

`StealResult` 不使用 `ConfigDict(from_attributes=True)`，因为它由 service 层构造的 dict 数据填充，不是从 ORM 模型直接转换。
