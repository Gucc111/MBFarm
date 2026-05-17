# `routes/auth.md` — 认证 API 路由层

## 1. 模块职责

本模块定义 MB Farm 用户认证相关的 HTTP API 端点，负责：

- **接收**前端提交的注册、登录、登出请求；
- **校验**请求参数的合法性（由 Pydantic Schema 层完成）；
- **调用** `services/auth_service.py` 执行认证业务逻辑；
- **管理**认证 Cookie 的写入（登录）与清除（登出）；
- **返回**标准化的 JSON 响应。

**不处理**的业务：

- 密码哈希（委托 `core/security.py`）；
- 数据库 CRUD（委托 `repositories/`）；
- 业务规则验证（委托 `services/auth_service.py`）。

---

## 2. 路由列表

> **路径前缀**: Router prefix `/auth` + `main.py` 挂载前缀 `/api` = 完整路径 `/api/auth/...`

| 方法 | 路径 | 描述 | 请求体 | 响应 | 异常 |
|------|------|------|--------|------|------|
| `POST` | `/api/auth/register` | 用户注册 | `UserCreate` | `201` + `UserResponse` | `409` 用户名重复, `422` 校验失败 |
| `POST` | `/api/auth/login` | 用户登录 | `UserLogin` | `200` + `LoginResponse` + `Set-Cookie` | `401` 凭证错误, `422` 校验失败 |
| `POST` | `/api/auth/logout` | 用户登出 | 无 | `200` + `{"message": "已登出"}` + `Clear-Cookie` | — |
| `GET` | `/api/auth/me` | 获取当前用户 | 无 | `200` + `UserResponse` | `401` 未认证 |

---

## 3. 请求/响应示例

### 3.1 注册 — `POST /api/auth/register`

**请求体：**

```json
{
  "username": "player1",
  "password": "SecurePass123!"
}
```

**成功响应 (`201`)：**

```json
{
  "id": 1,
  "username": "player1",
  "coins": 500,
  "xp": 0,
  "level": 1,
  "created_at": "2025-01-15T08:30:00Z"
}
```

**冲突响应 (`409`)：**

```json
{
  "error": {
    "code": "CONFLICT",
    "message": "用户名已存在"
  }
}
```

---

### 3.2 登录 — `POST /api/auth/login`

**请求体：**

```json
{
  "username": "player1",
  "password": "SecurePass123!"
}
```

**成功响应 (`200`)：**

```json
{
  "user": {
    "id": 1,
    "username": "player1",
    "coins": 500,
    "xp": 0,
    "level": 1,
    "created_at": "2025-01-15T08:30:00Z"
  },
  "message": "登录成功"
}
```

**同时设置 Cookie：**

```
Set-Cookie: session_token=abc123def456...; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800
```

**凭证错误响应 (`401`)：**

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "用户名或密码错误"
  }
}
```

---

### 3.3 登出 — `POST /api/auth/logout`

**请求体：** 无（从 Cookie 中读取 session_token）

**成功响应 (`200`)：**

```json
{
  "message": "已登出"
}
```

**同时清除 Cookie：**

```
Set-Cookie: session_token=; Path=/; Max-Age=0
```

---

### 3.4 获取当前用户 — `GET /api/auth/me`

**请求体：** 无（从 Cookie 中读取 session_token）

**成功响应 (`200`)：**

```json
{
  "id": 1,
  "username": "player1",
  "coins": 500,
  "xp": 0,
  "level": 1,
  "created_at": "2025-01-15T08:30:00Z"
}
```

**未认证响应 (`401`)：**

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "未登录"
  }
}
```

---

## 4. 实现方案

```python
"""Authentication API routes."""

from fastapi import APIRouter, Cookie, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import clear_session_cookie, set_session_cookie
from app.repositories.user_repo import SessionRepository, UserRepository
from app.schemas.user import UserCreate, UserLogin, LoginResponse, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["认证"])


def _get_service(db: AsyncSession) -> AuthService:
    """内联工厂函数：创建 AuthService 实例，共享同一 db 会话。"""
    return AuthService(db, UserRepository(db), SessionRepository(db))


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    service = _get_service(db)
    user = await service.register(user_data.username, user_data.password)
    return user


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="用户登录",
)
async def login(
    login_data: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    service = _get_service(db)
    session = await service.login(login_data.username, login_data.password)
    set_session_cookie(response, session.token)
    return LoginResponse(
        user=UserResponse.model_validate(session.user),
        message="登录成功",
    )


@router.post(
    "/logout",
    summary="用户登出",
)
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias="session_token"),
    db: AsyncSession = Depends(get_db),
):
    if session_token:
        session_repo = SessionRepository(db)
        session = await session_repo.get_by_token(session_token)
        if session:
            await session_repo.delete(session)

    resp = JSONResponse(content={"message": "已登出"})
    clear_session_cookie(resp)
    return resp


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="获取当前用户信息",
)
async def get_me(
    session_token: str | None = Cookie(default=None, alias="session_token"),
    db: AsyncSession = Depends(get_db),
):
    if not session_token:
        raise UnauthorizedError("未登录")

    service = _get_service(db)
    user = await service.get_current_user(session_token)
    return user
```

---

## 5. Cookie 流转说明

### 5.1 登录流程

```
Browser ── POST /api/auth/login ──→ Server
                     │                       │
                     │              AuthService.login()
                     │              验证凭证 + 创建 Session
                     │                       │
           ←── 200 + JSON + Set-Cookie ──── │
               session_token=xxx
```

### 5.2 后续请求携带 Cookie

```
Browser ── GET /api/auth/me ──→ Server
Cookie: session_token=xxx        │
                                 │  1. 从 Cookie 提取 token
                                 │  2. SessionRepository.get_by_token()
                                 │  3. 验证有效性
                                 │  4. UserRepository.get_by_id()
           ←── 200 + UserResponse │
```

### 5.3 Cookie 属性

| 属性 | 值 | 说明 |
|------|------|------|
| `Name` | `session_token` | 令牌名称 |
| `HttpOnly` | `true` | 禁止 JS 访问，防 XSS |
| `Secure` | `false`（开发）/ `true`（生产） | 开发环境为 HTTP |
| `SameSite` | `lax` | 防 CSRF |
| `Path` | `/` | 全站有效 |

---

## 6. 与 Services 层的集成

```
routes/auth.py                          services/auth_service.py
┌──────────────────────┐               ┌──────────────────────┐
│  _get_service(db)    │               │  register()          │
│  → AuthService(      │               │  ├─ user_repo.create()
│      db,             │               │  ├─ hash_password()
│      UserRepository, │               │  └─ 使用 INIT_USER 常量
│      SessionRepo)    │               │                       │
│                      │               │  login()              │
│  register            │               │  ├─ user_repo.find()
│  → service.register()│               │  ├─ verify_password()
│  → return User       │               │  ├─ delete_all旧session
│                      │               │  └─ session_repo.create()
│  login               │               │                       │
│  → service.login()   │               │  logout()             │
│  → set_session_cookie│               │  → session_repo.delete()
│  → LoginResponse     │               │                       │
│                      │               │  get_current_user()   │
│  logout              │               │  → session_repo.get_by_token()
│  → 清除 Cookie       │               │  → user_repo.get_by_id()
│                      │               │                       │
│  get_me              │               │                       │
│  → service.get_      │               │                       │
│     current_user()   │               │                       │
└──────────────────────┘               └──────────────────────┘
```

### 集成要点

1. **使用 `_get_service(db)` 内联工厂**：确保 Service 和两个 Repository 共享同一 `AsyncSession`
2. **Cookie 设置/清除在路由层完成**：关注点分离——路由负责 HTTP 协议细节，Service 负责业务逻辑
3. **异常由全局处理器统一转换**：`AppError` → JSON 响应（由 `main.py` 中的全局处理器处理）
4. **路由前缀**：Router `/auth` + `main.py` 挂载 `/api` = 完整路径 `/api/auth/...`

---

## 7. 后续扩展

- **验证码/防刷**：在注册接口前集成图形验证码；
- **多端登录限制**：在 `AuthService.login()` 中实现同一账号单点登录策略；
- **记住我**：区分短期 Session 和长期 Token，提供 `remember_me` 选项；
- **WebSocket 通知**：登录成功后建立 WebSocket 连接，推送偷菜/成熟提醒。
