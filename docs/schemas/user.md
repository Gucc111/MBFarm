# User Schemas

## 模块职责

`schemas/user.py` 定义了 FastAPI 请求/响应的数据验证模型（Pydantic v2）。
该模块位于 `schemas` 层，是 API 契约的核心载体——所有入参校验、出参序列化均以此为基准。

### 设计原则

- **防御式校验**：所有用户可控的输入都经过严格的 Pydantic 字段校验
- **敏感信息隔离**：`UserResponse` 明确排除 `password_hash` 等敏感字段
- **类型安全**：利用 Pydantic v2 类型提示实现编译期 + 运行期双重保障
- **OpenAPI 集成**：Schema 自动继承到 FastAPI 的 `/docs` 接口文档中

---

## Schema 列表

| 类名 | 用途 | 继承自 | 字段 |
|------|------|--------|------|
| `UserCreate` | 注册请求体 | `BaseModel` | `username`, `password` |
| `UserLogin` | 登录请求体 | `BaseModel` | `username`, `password` |
| `UserResponse` | 用户信息响应 | `BaseModel` | `id`, `username`, `coins`, `xp`, `level`, `created_at` |
| `LoginResponse` | 登录成功响应 | `BaseModel` | `user` (`UserResponse`), `message` |

---

## 字段校验规则

### UserCreate（注册）

| 字段 | 类型 | 校验规则 | 说明 |
|------|------|----------|------|
| `username` | `str` | `min_length=2`, `max_length=32`, 非空 | 用户名长度 2-32 字符 |
| `password` | `str` | `min_length=6`, `max_length=128`, 非空 | 密码最小 6 位，防止弱密码 |

### UserLogin（登录）

| 字段 | 类型 | 校验规则 | 说明 |
|------|------|----------|------|
| `username` | `str` | `min_length=2`, `max_length=32`, 非空 | 同注册 |
| `password` | `str` | `min_length=6`, `max_length=128`, 非空 | 同注册 |

### UserResponse（响应）

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `id` | `int` | `User.id` | 数据库自增主键 |
| `username` | `str` | `User.username` | 用户名 |
| `coins` | `int` | `User.coins` | 金币余额（默认 1000） |
| `xp` | `int` | `User.xp` | 经验值（默认 0） |
| `level` | `int` | `User.level` | 等级（默认 1） |
| `created_at` | `datetime` | `User.created_at` | 注册时间 |

**注意**：`UserResponse` 通过 `model_config` 的 `from_attributes=True`（Pydantic v2 对应 `model_config = ConfigDict(from_attributes=True)`）实现从 SQLAlchemy ORM 对象的自动转换。不包含 `password_hash`、`session_token` 等敏感字段。

### LoginResponse（登录响应）

| 字段 | 类型 | 说明 |
|------|------|------|
| `user` | `UserResponse` | 登录成功的用户信息 |
| `message` | `str` | 提示语，如 "Login successful" |

---

## 实现方案

```python
"""app/schemas/user.py

Pydantic v2 schemas for user authentication endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    """用户注册请求体"""

    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    """用户登录请求体"""

    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """用户信息响应（不含密码）"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    coins: int
    xp: int
    level: int
    created_at: datetime


class LoginResponse(BaseModel):
    """登录成功响应"""

    user: UserResponse
    message: str
```

### Pydantic v2 关键特性

| 特性 | 用途 | 代码对应 |
|------|------|----------|
| `Field(..., min_length=2, max_length=32)` | 字段级校验 | `username`、`password` 字段 |
| `ConfigDict(from_attributes=True)` | ORM 对象 → Pydantic 模型自动转换 | `UserResponse` |
| `model_config = ...` | Pydantic v2 配置方式（替代 v1 的 `Config` 内部类） | `UserResponse` |

### 与 Pydantic v1 的差异

```python
# Pydantic v1 (不使用)
class Config:
    from_attributes = True   # 旧版写法

# Pydantic v2 (使用)
model_config = ConfigDict(from_attributes=True)  # 新版写法
```

---

## 与 routes 的集成说明

### 注册端点 (`POST /api/auth/register`)

```python
# app/api/auth.py（示意）
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import register_user
from app.core.dependencies import get_db_service  # 假设的 DB 服务注入

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    payload: UserCreate,          # ← FastAPI 自动用 UserCreate 校验请求体
    db_service = Depends(get_db_service),
):
    user = await register_user(db_service, payload)
    return UserResponse.model_validate(user)  # ORM → Schema
```

### 登录端点 (`POST /api/auth/login`)

```python
@router.post("/login", response_model=LoginResponse)
async def login(
    payload: UserLogin,           # ← FastAPI 自动用 UserLogin 校验请求体
    db_service = Depends(get_db_service),
):
    user, message = await login_user(db_service, payload)
    return LoginResponse(user=UserResponse.model_validate(user), message=message)
```

### 请求/响应流程图

```
HTTP Request Body (JSON)
       │
       ▼
  ┌──────────────┐
  │ FastAPI      │   ← 自动反序列化 + Pydantic 校验
  │ (Body Parser)│   ← 校验失败返回 422 Unprocessable Entity
  └──────┬───────┘
         │ 合法数据 → UserCreate / UserLogin 实例
         ▼
  ┌──────────────┐
  │ AuthService  │   ← 业务逻辑：注册 / 登录
  │ (register)   │
  └──────┬───────┘
         │ SQLAlchemy ORM User 实例
         ▼
  ┌──────────────┐
  │ UserResponse │   ← model_validate() 转换 ORM → Pydantic
  └──────┬───────┘
         │
         ▼
  HTTP Response Body (JSON)
```

---

## 错误处理

| 场景 | HTTP 状态码 | 响应示例 |
|------|------------|----------|
| 校验失败（如 username 为空） | `422` | `{"detail": [{"type": "missing", "loc": ["body", "username"], "msg": "Field required"}]}` |
| 校验失败（如 password < 6 位） | `422` | `{"detail": [{"type": "string_too_short", "loc": ["body", "password"], "msg": "String should have at least 6 characters"}]}` |
| 用户名已存在 | `409` | `{"detail": "Username already exists"}` （由 AuthService 抛出） |

---

## 扩展规划

| 方向 | 说明 |
|------|------|
| 用户信息更新 | 新增 `UserUpdate` Schema（部分字段可选：`coins`, `xp`, `level`） |
| 密码修改 | 新增 `PasswordChange` Schema（`old_password`, `new_password`） |
| 分页查询 | 新增 `UserListResponse` Schema（`items: list[UserResponse]`, `total: int`） |
| 邮箱/手机号 | 新增 `email`、`phone` 字段及对应校验（`EmailStr` 类型） |

---

## 文件位置

| 文件 | 路径 |
|------|------|
| 源代码 | `app/schemas/user.py` |
| 本档 | `docs/p0/schemas/user.md` |
| 父档 | `docs/p0/overview.md` |
