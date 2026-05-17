# AuthService — 认证业务逻辑

> **模块定位**: `app/services/auth_service.py`
>
> 封装用户注册、登录、登出三大认证流程的全部业务规则，是 P0 阶段的核心业务层。

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **用户注册** | 校验用户名唯一性、密码强度，哈希密码后创建用户记录 |
| **用户登录** | 校验用户存在性和密码正确性，创建 Session 并返回 token |
| **用户登出** | 根据 Session token 删除对应会话记录 |
| **业务规则封装** | 所有认证相关的业务逻辑集中于此，Route 层仅负责参数解析和响应组装 |

---

## 2. 设计决策

### 2.1 厚服务（Thick Service）

本项目采用 **厚服务** 设计模式——Service 层持有完整的业务逻辑，Repository 和 Model 仅负责数据存取。

| 维度 | 厚服务 | 瘦服务 |
|------|--------|--------|
| **逻辑位置** | 集中在 AuthService | 分散在各层 |
| **可测试性** | 只需 mock Repository | 需要 mock 多层的交互 |
| **一致性** | 业务规则单一来源 | 容易在不同 Route 中出现不一致 |
| **适合场景** | 小型项目（10-20 人） | 大型分布式系统 |

**结论**：MB Farm 作为小型局域网项目，厚服务更简洁、易维护。

### 2.2 构造函数依赖注入

`AuthService` 通过构造函数接收 `AsyncSession`、`UserRepository` 和 `SessionRepository`，而非通过每个方法单独传入：

```python
class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        user_repo: UserRepository,
        session_repo: SessionRepository,
    ):
        self.db = db
        self.user_repo = user_repo
        self.session_repo = session_repo
```

**理由**：
- 一个认证流程（注册/登录/登出）可能涉及多次 Repository 调用，共享同一个 `db` 会话
- 保证同一操作中的所有数据库操作在同一个事务内
- 避免每个方法都写一遍 `db = Depends(get_db)` 的重复代码

### 2.3 异常处理策略

所有认证相关的业务异常通过 `core/exceptions` 模块抛出：

| 场景 | 异常 | HTTP 状态码 |
|------|------|-------------|
| 用户名已存在 | `ConflictError("用户名已存在")` | 409 |
| 用户不存在 | `NotFoundError("用户不存在")` | 404 |
| 密码错误 | `UnauthorizedError("用户名或密码错误")` | 401 |
| 密码太短 | `AppValidationError("密码长度至少 6 个字符")` | 422 |

这些异常在 `main.py` 中由全局异常处理器统一转换为 JSON 响应，**Route 层无需手动 try/except**。

---

## 3. 方法列表

### 3.1 `AuthService`

| 方法 | 参数 | 返回值 | 异常 | 说明 |
|------|------|--------|------|------|
| `register` | `username: str`, `password: str` | `User` | `ConflictError`, `AppValidationError` | 注册新用户 |
| `login` | `username: str`, `password: str` | `Session` | `NotFoundError`, `UnauthorizedError` | 用户登录 |
| `logout` | `session: Session` | `None` | `UnauthorizedError` | 用户登出 |

---

### 3.2 `register(username, password) → User`

注册用户，执行以下校验和流程：

1. **用户名唯一性校验** — 查询 `user_repo.get_by_username()`，已存在则抛 `ConflictError`
2. **密码强度校验** — 长度至少 6 字符，不足则抛 `AppValidationError`
3. **密码哈希** — 调用 `security.hash_password()` 将明文密码转为 bcrypt 哈希
4. **创建用户** — 调用 `user_repo.create()` 写入数据库
5. **返回 User 对象**

```
register(username, password)
    │
    ├─── user_repo.get_by_username(username)
    │       │
    │       └── 存在? → ConflictError("用户名已存在")
    │
    ├─── len(password) < 6
    │       └── 是 → AppValidationError("密码长度至少 6 个字符")
    │
    ├─── security.hash_password(password) → password_hash
    │
    ├─── user_repo.create({username, password_hash})
    │       │
    │       └── 写入 users 表
    │
    └── 返回 User 对象
```

---

### 3.3 `login(username, password) → Session`

用户登录，执行以下校验和流程：

1. **查找用户** — 查询 `user_repo.get_by_username()`，不存在则抛 `NotFoundError`
2. **密码验证** — 调用 `security.verify_password()`，不匹配则抛 `UnauthorizedError`
3. **生成 Token** — 调用 `str(uuid.uuid4())` 生成 Session token
4. **创建 Session** — 调用 `session_repo.create()` 写入 sessions 表，过期时间默认 7 天
5. **返回 Session 对象**

```
login(username, password)
    │
    ├─── user_repo.get_by_username(username)
    │       │
    │       └── 不存在? → NotFoundError("用户不存在")
    │
    ├─── security.verify_password(password, user.password_hash)
    │       │
    │       └── 不匹配? → UnauthorizedError("用户名或密码错误")
    │
    ├─── str(uuid.uuid4()) → token
    │
    ├─── datetime.utcnow() + timedelta(days=7) → expires_at
    │
    ├─── session_repo.create(user.id, token, expires_at)
    │       │
    │       └── 写入 sessions 表
    │
    └── 返回 Session 对象
```

---

### 3.4 `logout(session: Session) → None`

用户登出，执行以下流程：

1. **Session 有效性校验** — 调用 `session.is_expired()`，已过期则抛 `UnauthorizedError`
2. **删除 Session** — 调用 `session_repo.delete()` 删除对应记录

```
logout(session)
    │
    ├─── session.is_expired()
    │       │
    │       └── 已过期? → UnauthorizedError("登录已过期")
    │
    ├─── session_repo.delete(session)
    │       │
    │       └── 删除 sessions 表记录
    │
    └── 返回 None
```

---

## 4. 实现方案

完整 Python 实现代码：

```python
"""
AuthService

认证业务逻辑层，封装用户注册、登录、登出流程。
通过构造函数注入依赖，确保同一操作内的数据库操作在同一个事务内。
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AppValidationError,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
)
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.models.session import Session
from app.repositories.user_repo import UserRepository, SessionRepository


class AuthService:
    """认证服务：处理注册、登录、登出等业务逻辑。"""

    def __init__(
        self,
        db: AsyncSession,
        user_repo: UserRepository,
        session_repo: SessionRepository,
    ):
        self.db = db
        self.user_repo = user_repo
        self.session_repo = session_repo

    async def register(self, username: str, password: str) -> User:
        """
        注册新用户。

        业务规则：
        1. 用户名不得重复
        2. 密码长度至少 6 个字符
        3. 密码需经 bcrypt 哈希后存储

        Args:
            username: 用户名（32 字符以内，由 Route 层 Pydantic 校验）
            password: 明文密码

        Returns:
            创建成功的 User 对象

        Raises:
            ConflictError: 用户名已存在
            AppValidationError: 密码强度不达标
        """
        # 1. 用户名唯一性校验
        existing = await self.user_repo.get_by_username(username)
        if existing:
            raise ConflictError("用户名已存在")

        # 2. 密码强度校验
        if len(password) < 6:
            raise AppValidationError("密码长度至少 6 个字符")

        # 3. 密码哈希 + 创建用户
        password_hash = hash_password(password)
        user = await self.user_repo.create({
            "username": username,
            "password_hash": password_hash,
            "coins": 500,    # 新手初始金币
            "xp": 0,         # 新手初始经验值
            "level": 1,      # 新手初始等级
        })

        return user

    async def login(self, username: str, password: str) -> Session:
        """
        用户登录。

        业务规则：
        1. 用户必须存在
        2. 密码必须匹配
        3. 登录成功后创建新 Session（默认 7 天过期）
        4. 自动清理该用户的所有旧 Session（单设备限制）

        Args:
            username: 用户名
            password: 明文密码

        Returns:
            创建成功的 Session 对象

        Raises:
            NotFoundError: 用户不存在
            UnauthorizedError: 密码错误
        """
        # 1. 查找用户
        user = await self.user_repo.get_by_username(username)
        if not user:
            raise NotFoundError("用户不存在")

        # 2. 密码验证
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("用户名或密码错误")

        # 3. 清理该用户的所有旧 Session（单设备限制）
        await self.session_repo.delete_all_by_user_id(user.id)

        # 4. 生成 Token 并创建新 Session
        token = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=7)

        session = await self.session_repo.create(user.id, token, expires_at)
        return session

    async def logout(self, session: Session) -> None:
        """
        用户登出。

        业务规则：
        1. Session 必须有效（未过期）
        2. 删除对应 Session 记录

        Args:
            session: 当前 Session 对象

        Raises:
            UnauthorizedError: Session 已过期
        """
        if session.is_expired():
            # 已过期则直接删除（清理），不再返回
            await self.session_repo.delete(session)
            return

        await self.session_repo.delete(session)
```

---

## 5. 与 Routes 层的集成

### 5.1 Route 层调用方式

Route 层通过 FastAPI 依赖注入获取 `AuthService` 所需的依赖，调用流程如下：

```python
# app/api/routes/auth.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.database import get_db
from app.core.exceptions import (
    AppValidationError,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
)
from app.models.session import Session as SessionModel
from app.schemas.user import UserCreate, UserLogin
from app.services.auth_service import AuthService
from app.repositories.user_repo import UserRepository, SessionRepository

router = APIRouter(prefix="/auth", tags=["认证"])


def get_auth_service(
    db: AsyncSession = Depends(get_db),
) -> AuthService:
    """依赖注入：构建 AuthService 实例。"""
    user_repo = UserRepository(db)
    session_repo = SessionRepository(db)
    return AuthService(db=db, user_repo=user_repo, session_repo=session_repo)


@router.post("/register")
async def register(
    data: UserCreate,
    service: AuthService = Depends(get_auth_service),
):
    """用户注册接口。"""
    user = await service.register(data.username, data.password)
    return {"message": "注册成功", "user_id": user.id, "coins": user.coins}


@router.post("/login")
async def login(
    data: UserLogin,
    service: AuthService = Depends(get_auth_service),
):
    """用户登录接口。"""
    session = await service.login(data.username, data.password)

    response = JSONResponse(content={"message": "登录成功", "user_id": session.user_id})
    response.set_cookie(
        key="session_token",
        value=session.token,
        max_age=604800,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout")
async def logout(
    service: AuthService = Depends(get_auth_service),
    request: Request = None,
):
    """用户登出接口。"""
    token = request.cookies.get("session_token")
    if not token:
        raise UnauthorizedError("未登录")

    # 查询 Session（不依赖 session_repo，直接通过 token 查找）
    session = await service.session_repo.get_by_token(token)
    if not session:
        raise UnauthorizedError("登录已过期")

    await service.logout(session)

    response = JSONResponse(content={"message": "登出成功"})
    response.delete_cookie(key="session_token", path="/")
    return response
```

### 5.2 依赖注入图

```
Route (auth.py)
    │
    ├── Depends(get_auth_service)
    │       │
    │       ├── get_db() → AsyncSession
    │       │
    │       ├── UserRepository(db)
    │       │       │
    │       │       └── User model, async queries
    │       │
    │       ├── SessionRepository(db)
    │       │       │
    │       │       └── Session model, async queries
    │       │
    │       └── AuthService(db, user_repo, session_repo)
    │               │
    │               ├── hash_password / verify_password  (core/security)
    │               └── ConflictError / NotFoundError etc (core/exceptions)
```

### 5.3 异常处理流

```
Route 调用 service.register() / service.login() / service.logout()
    │
    ├── 业务异常（ConflictError / NotFoundError / UnauthorizedError）
    │       │
    │       └── 不捕获，向上传播
    │
    └── main.py 全局异常处理器
            │
            └── 转换为 JSONResponse(status_code, {"error": {"code", "message"}})
```

**关键约定**：Route 层**不捕获** `AppError` 子类异常，交由 `main.py` 的全局异常处理器统一处理。

---

## 6. Cookie 与 Session 流转

完整登录-访问-登出的 Cookie 流转过程：

```
┌──────────┐     1. POST /auth/register      ┌──────────┐
│  Browser  │ ──────────────────────────────> │  Server  │
│          │                                 │          │
│          │     2. 200 OK {"user_id": 1}    │          │
│          │ <────────────────────────────── │          │
│          │                                 │          │
│          │     3. POST /auth/login         │          │
│          │ ──────────────────────────────> │          │
│          │                                 │          │
│          │     4. 200 OK, Set-Cookie       │          │
│          │        session_token=xxx        │          │
│          │ <────────────────────────────── │          │
│          │                                 │          │
│          │     5. GET /farm,               │          │
│          │        Cookie: session_token=xx │          │
│          │ ──────────────────────────────> │          │
│          │                                 │          │
│          │     6. get_session(token)       │          │
│          │        → Session 有效           │          │
│          │ <────────────────────────────── │          │
│          │                                 │          │
│          │     7. POST /auth/logout        │          │
│          │ ──────────────────────────────> │          │
│          │                                 │          │
│          │     8. 200 OK, Delete-Cookie    │          │
│          │ <────────────────────────────── │          │
└──────────┘                                 └──────────┘
```

---

## 7. 后续扩展

| 功能 | 方案 | 状态 |
|------|------|------|
| **图形验证码** | 注册时校验验证码，调用 `captcha_service.verify()` | 待实现 |
| **登录限流** | 同一 IP 短时间内多次失败登录则临时封禁 | 待实现 |
| **记住我** | 延长 Session 过期时间（30 天 vs 7 天） | 待实现 |
| **登录日志** | 每次登录成功/失败记录到 `login_log` 表 | 待实现 |
| **社交登录** | QQ OAuth 登录，注册时自动绑定用户 | 远期规划 |
| **多设备支持** | 允许同一用户同时登录 N 个设备 | 待实现（需移除 `delete_all_by_user_id`） |

---

## 8. 相关文档

| 文档 | 路径 | 关系 |
|------|------|------|
| 用户 & Session 模型 | `docs/p0/models/user.md` | AuthService 操作的数据模型 |
| Security 安全基础设施 | `docs/p0/core/security.md` | AuthService 使用的密码哈希工具 |
| 业务异常 | `docs/p0/core/exceptions.md` | AuthService 抛出的异常类型 |
| UserRepository | `docs/p0/repositories/user_repo.md` | AuthService 注入的数据访问层 |
| 数据库依赖 | `docs/p0/core/database.md` | AuthService 获取 AsyncSession 的来源 |
| 配置管理 | `docs/p0/core/config.md` | Session 过期时间等配置来源 |
