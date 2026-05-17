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

| 方法 | 路径 | 描述 | 请求体 | 响应 | 异常 |
|------|------|------|--------|------|------|
| `POST` | `/auth/register` | 用户注册 | `UserCreate` | `201` + `UserResponse` | `409` 用户名重复, `422` 校验失败 |
| `POST` | `/auth/login` | 用户登录 | `UserLogin` | `200` + `LoginResponse` + `Set-Cookie` | `401` 凭证错误, `422` 校验失败 |
| `POST` | `/auth/logout` | 用户登出 | 无 | `200` + `{"message": "已登出"}` + `Clear-Cookie` | — |
| `GET` | `/auth/me` | 获取当前用户 | 无 | `200` + `UserResponse` | `401` 未认证 |

---

## 3. 请求/响应示例

### 3.1 注册 — `POST /auth/register`

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
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "username": "player1",
  "gold": 100,
  "energy": 100,
  "created_at": "2025-01-15T08:30:00Z"
}
```

**冲突响应 (`409`)：**

```json
{
  "detail": "用户名已存在"
}
```

---

### 3.2 登录 — `POST /auth/login`

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
  "message": "登录成功",
  "user": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "username": "player1",
    "gold": 100,
    "energy": 100,
    "created_at": "2025-01-15T08:30:00Z"
  }
}
```

**同时设置 Cookie：**

```
Set-Cookie: session_token=abc123def456...; HttpOnly; Secure; SameSite=Lax; Path=/
```

**凭证错误响应 (`401`)：**

```json
{
  "detail": "用户名或密码错误"
}
```

---

### 3.3 登出 — `POST /auth/logout`

**请求体：** 无

**成功响应 (`200`)：**

```json
{
  "message": "已登出"
}
```

**同时清除 Cookie：**

```
Set-Cookie: session_token=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0
```

---

### 3.4 获取当前用户 — `GET /auth/me`

**请求体：** 无

**成功响应 (`200`)：**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "username": "player1",
  "gold": 100,
  "energy": 100,
  "created_at": "2025-01-15T08:30:00Z"
}
```

**未认证响应 (`401`)：**

```json
{
  "detail": "未登录"
}
```

---

## 4. 实现方案

完整实现代码：

```python
"""
app/routes/auth.py — 认证 API 路由

定义用户注册、登录、登出和获取当前用户信息的 RESTful 端点。
"""

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.exceptions import AppHTTPException
from app.schemas.user import UserCreate, UserResponse, UserLogin, LoginResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
)
async def register(
    user_data: UserCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    注册新用户。

    - `username`: 唯一用户名，3-32 位字母数字及下划线；
    - `password`: 明文密码，6-128 位，注册时会在 `AuthService` 中哈希。

    返回创建的 `UserResponse`（不包含密码字段）。
    """
    service = AuthService(db)

    try:
        user = await service.register(user_data)
    except AppHTTPException as e:
        if e.code == 409:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名已存在",
            )
        raise HTTPException(
            status_code=e.code,
            detail=e.message,
        )

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
    """
    用户登录，成功后设置 `session_token` Cookie。

    - `username`: 注册时的用户名；
    - `password`: 注册时的明文密码。

    返回登录响应 + `Set-Cookie` 头。
    """
    service = AuthService(db)

    try:
        user, session_token = await service.login(login_data)
    except AppHTTPException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

    return LoginResponse(
        message="登录成功",
        user=user,
    )


@router.post(
    "/logout",
    summary="用户登出",
)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    # 需要用户已认证才能登出
    # _ = Depends(get_current_user),  # 取消注释以启用强制认证
):
    """
    用户登出，清除 `session_token` Cookie。
    """
    response.set_cookie(
        key="session_token",
        value="",
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=0,
    )

    return {"message": "已登出"}


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="获取当前用户信息",
)
async def get_current_user_info(
    db: AsyncSession = Depends(get_db),
    # 需要用户已认证
    # current_user = Depends(get_current_user),  # 取消注释以启用强制认证
):
    """
    获取当前已认证用户的信息。

    需要依赖 `core/dependencies.py` 中定义的 `get_current_user` 依赖，
    该依赖从 Cookie 中提取 `session_token` 并验证有效性。
    """
    # 以下代码在实现 get_current_user 后可直接使用：
    # return current_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录",
    )
```

---

## 5. Cookie 流转说明

### 5.1 登录流程

```
┌──────────┐          ┌──────────────┐          ┌──────────────┐
│  前端     │          │  auth 路由层  │          │ auth_service  │
│  (浏览器)  │          │  (app/routes) │          │  (app/services)│
└────┬─────┘          └──────┬───────┘          └──────┬───────┘
     │                       │                         │
     │  POST /auth/login     │                         │
     │  {username, password} │                         │
     ├──────────────────────►│                         │
     │                       │  AuthService.login()    │
     │                       ├────────────────────────►│
     │                       │                         │
     │                       │  (验证凭证)              │
     │                       │                         │
     │                       │  (生成 session_token)     │
     │                       │                         │
     │  200 + JSON           │                         │
     │  + Set-Cookie         │                         │
     │  header               │                         │
     │◄──────────────────────┤                         │
     │                       │                         │
     │  浏览器自动存储 Cookie │                         │
     └───────────────────────┴─────────────────────────┘
```

### 5.2 后续请求携带 Cookie

```
┌──────────┐          ┌──────────────┐
│  前端     │          │  auth 路由层  │
│  (浏览器)  │          │  (app/routes) │
└────┬─────┘          └──────┬───────┘
     │                       │
     │  GET /auth/me         │
     │  Cookie:              │
     │  session_token=xxx    │
     ├──────────────────────►│
     │                       │  get_current_user 依赖:
     │                       │  1. 从 Cookie 提取 token
     │                       │  2. 查询 Session 模型
     │                       │  3. 验证 token 有效性
     │                       │  4. 返回 User 对象
     │                       │
     │  200 + UserResponse   │
     │◄──────────────────────┤
```

### 5.3 Cookie 属性

| 属性 | 值 | 说明 |
|------|------|------|
| `Name` | `session_token` | 令牌名称 |
| `HttpOnly` | `true` | 禁止 JS 访问，防 XSS |
| `Secure` | `true` | 仅 HTTPS 传输（开发环境可设为 `false`） |
| `SameSite` | `lax` | 防 CSRF，允许顶级导航 GET 请求 |
| `Path` | `/` | 全站有效 |
| `Max-Age` | 可选 | 会话结束后自动过期 |

---

## 6. 与 Services 层的集成

```
routes/auth.py                          services/auth_service.py
┌──────────────────────┐               ┌──────────────────────┐
│  register()          │               │  register()          │
│  ├─ user_data: UserCreate          │  ├─ user_repo.create() │
│  ├─ AuthService(db)                │  ├─ security.hash()    │
│  └─ return UserResponse            │  └─ return User        │
│                                    │                       │
│  login()                     │     │  login()               │
│  ├─ login_data: UserLogin    │     │  ├─ user_repo.find()   │
│  ├─ AuthService(db)          │     │  ├─ security.verify()  │
│  ├─ return (user, token)     │     │  ├─ session_repo.create()
│  └─ (由路由设置 Cookie)       │     │  └─ return (user, token)
│                                    │                       │
│  logout()                      │     │  (注销逻辑可选在此)    │
│  └─ (由路由清除 Cookie)         │     │                       │
└──────────────────────┘               └──────────────────────┘
```

### 集成要点

1. **每次请求创建 `AuthService` 实例**（轻量，仅持有 `AsyncSession` 引用）；
2. **`AuthService` 通过 DI 获取 `AsyncSession`**，避免连接泄漏；
3. **认证 Cookie 的设置/清除**在路由层完成（关注点分离：路由负责 HTTP 协议细节，Service 负责业务逻辑）；
4. **异常映射**：`AppHTTPException` 被转换为 `HTTPException`，确保前端接收到标准的 FastAPI 错误格式。

---

## 7. 后续扩展

- **验证码/防刷**：在注册接口前集成图形验证码或手机/邮箱验证；
- **多端登录限制**：在 `AuthService.login()` 中实现同一账号单点登录策略；
- **记住我**：区分短期 Session 和长期 Token，提供 `remember_me` 选项；
- **WebSocket 通知**：登录成功后建立 WebSocket 连接，推送偷菜/成熟提醒。
