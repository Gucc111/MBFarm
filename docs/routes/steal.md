# Route: Steal

## 模块职责

`app/routes/steal.py` — 偷菜相关 API 端点。

路由在 `main.py` 中以 `prefix="/steal"` 注册，`main.py` 统一添加 `/api` 前缀，因此最终路径为 `/api/steal/...`。

---

## API 端点列表

| Method | Path | 功能 | 认证 |
|---|---|---|---|
| `POST` | `/api/steal/{target_user_id}` | 偷取目标用户作物 | ✅ |
| `GET` | `/api/steal/my` | 查看我偷了谁的 | ✅ |
| `GET` | `/api/steal/me` | 查看谁偷了我 | ✅ |

---

## 端点详情

### `POST /api/steal/{target_user_id}`

偷取目标用户的成熟作物。

**路径参数:**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `target_user_id` | int | ✅ | 目标用户 ID |

**请求体:** 无

**响应体 (200) — `StealResult`:**

```json
{
  "seed_type": "wheat",
  "seed_name": "小麦",
  "quantity": 1,
  "value": 18
}
```

**错误响应:**

| 状态码 | 错误信息 |
|---|---|
| 403 | 不能偷自己 / 只能偷好友的作物 |
| 404 | 目标无成熟作物 / 用户不存在 |
| 409 | 今日偷菜次数已达上限 |
| 422 | 偷菜冷却中 / 体力不足 |

---

### `GET /api/steal/my`

查看我偷了谁的作物（不分页，返回全部记录，按时间倒序）。

**响应体 (200) — `StealHistoryResponse`:**

```json
{
  "records": [
    {
      "id": 1,
      "stealer_id": 1,
      "victim_id": 2,
      "stolen_crop_type": "wheat",
      "quantity": 1,
      "stolen_at": "2025-07-10T10:00:00+00:00"
    }
  ],
  "total": 15
}
```

---

### `GET /api/steal/me`

查看谁偷了我（不分页，返回全部记录，按时间倒序）。

**响应体 (200) — `StealHistoryResponse`:**

```json
{
  "records": [
    {
      "id": 1,
      "stealer_id": 2,
      "victim_id": 1,
      "stolen_crop_type": "carrot",
      "quantity": 1,
      "stolen_at": "2025-07-10T10:00:00+00:00"
    }
  ],
  "total": 3
}
```

---

## 完整路由代码

```python
"""Steal API routes — steal crops from friends."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.steal import StealHistoryResponse, StealResult
from app.services.steal import StealService

router = APIRouter(prefix="/steal", tags=["偷菜"])


def _get_service(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StealService:
    return StealService(db)


@router.post(
    "/{target_user_id}",
    response_model=StealResult,
    status_code=status.HTTP_200_OK,
    summary="偷菜",
)
async def steal_crop(
    target_user_id: int,
    svc: StealService = Depends(_get_service),
    user: User = Depends(get_current_user),
):
    """偷取目标用户的成熟作物。"""
    return await svc.steal(user.id, target_user_id)


@router.get(
    "/my",
    response_model=StealHistoryResponse,
    summary="我偷了谁的",
)
async def get_my_stolen(
    svc: StealService = Depends(_get_service),
    user: User = Depends(get_current_user),
):
    """查看我偷了谁的作物。"""
    return await svc.get_my_stolen(user.id)


@router.get(
    "/me",
    response_model=StealHistoryResponse,
    summary="谁偷了我",
)
async def get_being_stolen(
    svc: StealService = Depends(_get_service),
    user: User = Depends(get_current_user),
):
    """查看谁偷了我。"""
    return await svc.get_being_stolen(user.id)
```

---

## 错误码汇总

| HTTP 状态码 | 场景 |
|---|---|
| 200 | 偷菜成功 / 查询成功 |
| 401 | 未认证 |
| 403 | 偷自己 / 不是好友 |
| 404 | 无成熟作物 / 用户不存在 |
| 409 | 达到每日偷菜上限 |
| 422 | 偷菜冷却中 / 体力不足 |

---

## 使用示例

```bash
# 偷菜
curl -X POST -b "session_token=xxx" \
  http://localhost:8000/api/steal/2

# 查看我偷了谁的
curl -b "session_token=xxx" \
  http://localhost:8000/api/steal/my

# 查看谁偷了我
curl -b "session_token=xxx" \
  http://localhost:8000/api/steal/me
```

---

## 设计决策

### 路径参数 vs 请求体

`target_user_id` 作为路径参数（`/{target_user_id}`），而非请求体字段。这避免了请求体的需要，使得偷菜操作可以通过简单的 POST 调用完成。

### 不指定地块

当前实现不支持指定偷哪个地块（无 `plot_index` 参数）。从目标用户所有成熟作物中随机选取。如后续需要，可在 `steal` 方法中添加 `plot_index` 参数。

### 不分页

`/my` 和 `/me` 返回所有记录（不分页）。考虑到偷菜频率较低（每日上限 3 次），记录量不大。如后续需要分页，可在 service 层添加 `limit/offset` 参数。
