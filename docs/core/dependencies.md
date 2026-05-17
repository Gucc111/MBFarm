# 依赖注入 (DI) 基础设施模块

> 模块定位：`app/core/dependencies.py`
> 本文档描述该模块的设计、接口与使用方式。

---

## 1. 模块职责

本模块提供 **FastAPI 依赖注入工厂函数**，将基础设施组件（数据库会话、用户仓库、认证服务等）以声明式方式注入到 API 路由和业务逻辑中。

核心职责：

- 提供 `AsyncSession` 生命周期管理（请求级会话创建与关闭）
- 提供当前认证用户的解析逻辑（从 Cookie session token → `User` 实例）
- 作为整个应用依赖链的 **根入口**，其他服务通过构造函数注入依赖

---

## 2. 设计决策

### 2.1 为什么用构造函数注入 + `Depends`？

| 方案 | 优点 | 缺点 |
|------|------|------|
| **构造函数注入 + FastAPI `Depends`** | 显式依赖、天然可测试、IDE 友好、单元测试无需启动应用 | 需要为每个依赖写一个工厂函数 |
| **ServiceLocator 模式** | 按需获取，代码简洁 | 隐式依赖、难以追踪、不可测试、耦合紧 |

MB Farm 采用 **构造函数注入**（业务服务层） + **FastAPI `Depends`**（框架层绑定），两者互补：

- **框架层**（Routes → Depends）：FastAPI 在请求生命周期中自动创建、传递、清理依赖。
- **业务层**（Services → 构造函数）：服务实例在应用启动时组装，依赖通过构造函数传入，保持纯粹。

### 2.2 不用 ServiceLocator

MB Farm 规模较小（十几人），不需要复杂的 IoC 容器。ServiceLocator 带来的隐式依赖成本远大于收益。

---

## 3. DI 工厂函数列表

### 3.1 `get_db() → AsyncSession`

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    请求级数据库会话工厂。
    
    FastAPI 会在请求开始前创建会话，请求结束后自动关闭。
    如果请求过程中抛出异常，会话会自动回滚。
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

- **返回类型**：`AsyncSession`（SQLAlchemy 2.0 异步会话）
- **生命周期**：单个 HTTP 请求
- **清理**：请求结束时自动 `close()`
- **异常处理**：出错时自动 `rollback()` 并重新抛出

### 3.2 `get_current_user() → User`

```python
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    session_token: str = Cookie(None),
) -> User:
    """
    从 Cookie 中的 session token 解析当前认证用户。
    
    返回:
        User 实例（已验证）
    
    异常:
        HTTP 401：未提供 token 或 token 无效/过期
    """
    if not session_token:
        raise HTTPException(status_code=401, detail="未登录")
    
    session = await auth_service.get_session_by_token(db, session_token)
    if not session or session.is_expired():
        raise HTTPException(status_code=401, detail="会话已过期")
    
    user = await user_repo.get_user_by_id(db, session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    
    return user
```

- **返回类型**：`User` 模型实例
- **依赖**：`get_db`（传入 `AsyncSession`）
- **认证来源**：Cookie `session_token`
- **鉴权逻辑**：验证 token 有效性 + 关联用户存在性

### 3.3 `get_user_repo(db: AsyncSession) → UserRepository`

```python
def get_user_repo(db: AsyncSession = Depends(get_db)) -> UserRepository:
    """工厂函数：创建用户仓库实例，注入数据库会话。"""
    return UserRepository(db)
```

### 3.4 `get_auth_service(repo: UserRepository = Depends(get_user_repo)) -> AuthService`

```python
def get_auth_service(repo: UserRepository = Depends(get_user_repo)) -> AuthService:
    """工厂函数：创建认证服务实例，注入用户仓库。"""
    return AuthService(repo)
```

> 注：`AuthService` 内部可能还依赖 `security.py` 中的密码哈希和 session 生成函数，这些作为纯函数直接在构造函数中传入或通过模块导入使用。

---

## 4. 依赖链

```
┌─────────────────────────────────────────────────────────┐
│                      HTTP Request                        │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              API Route (e.g. /api/farm/status)            │
│                                                          │
│  @router.get("/status")                                   │
│  async def get_status(                                    │
│      user: User = Depends(get_current_user),             │
│  ): ...                                                   │
└────────────────────────┬────────────────────────────────┘
                         │ Depends
                         ▼
┌─────────────────────────────────────────────────────────┐
│           get_current_user()                              │
│                                                          │
│  1. 从 Cookie 读取 session_token                           │
│  2. 验证 token 有效性                                      │
│  3. 返回 User 实例                                        │
│                                                          │
│  依赖: Depends(get_db)                                   │
└────────────────────────┬────────────────────────────────┘
                         │ Depends
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  get_db()                                 │
│                                                          │
│  创建 AsyncSession，请求结束后自动关闭                     │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│            AsyncSession (SQLAlchemy)                      │
│                                                          │
│          SQLite Database File                            │
└─────────────────────────────────────────────────────────┘
```

业务服务层组装（应用启动时）：

```
Application Startup
       │
       ├── UserRepository(db=async_session_factory)
       │
       └── AuthService(repo=UserRepository)
              │
              └── (纯函数: hash_password, generate_session_token)
```

---

## 5. 实现方案

### 5.1 完整接口说明

```python
# app/core/dependencies.py

from typing import AsyncGenerator
from fastapi import Depends, HTTPException, Cookie, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.auth_service import AuthService


# ============================================================
# 1. 数据库会话工厂
# ============================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """请求级 AsyncSession 工厂。"""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# ============================================================
# 2. 当前认证用户解析
# ============================================================

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Cookie(None, alias="session_token"),
) -> User:
    """从 Cookie session_token 验证并返回当前用户。"""
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证信息",
            headers={"WWW-Authenticate": "Cookie"},
        )

    # 通过 AuthService 验证 session
    auth_service = AuthService(UserRepository(db))
    session = await auth_service.get_session_by_token(session_token)

    if not session or session.is_expired():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已过期或无效",
        )

    # 获取关联用户
    user = await UserRepository(db).get_user_by_id(session.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    return user


# ============================================================
# 3. 业务服务工厂（按需使用）
# ============================================================

def get_user_repo(
    db: AsyncSession = Depends(get_db),
) -> UserRepository:
    """工厂函数：返回 UserRepository 实例。"""
    return UserRepository(db)


def get_auth_service(
    repo: UserRepository = Depends(get_user_repo),
) -> AuthService:
    """工厂函数：返回 AuthService 实例。"""
    return AuthService(repo)
```

### 5.2 数据库会话生命周期

```
请求到达
   │
   ▼
get_db() 创建 AsyncSession
   │
   ▼
路由处理（读/写数据库）
   │
   ├── 正常完成 → yield 返回 → 请求结束 → session.close()
   │
   └── 异常抛出 → rollback() → 重新抛出异常 → session.close()
```

---

## 6. 使用方式

### 6.1 路由中获取当前用户

```python
# app/api/routes/auth_routes.py
from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/farm", tags=["farm"])

@router.get("/status")
async def get_farm_status(user: User = Depends(get_current_user)):
    """需要登录才能访问的端点。"""
    return {
        "user_id": user.id,
        "username": user.username,
        "coins": user.coins,
        # ...
    }
```

### 6.2 路由中直接注入数据库会话

```python
from app.core.dependencies import get_db
from sqlalchemy.ext.asyncio import AsyncSession

@router.get("/leaderboard")
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    """不需要认证，只需数据库访问。"""
    # 直接在路由中操作数据库
    ...
```

### 6.3 路由中注入业务服务

```python
from app.core.dependencies import get_auth_service
from app.services.auth_service import AuthService

@router.post("/login")
async def login(
    credentials: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """登录端点，直接调用 AuthService。"""
    user = await auth_service.authenticate(credentials.username, credentials.password)
    # ...
```

### 6.4 可选认证端点

对于某些端点，用户可选择登录（未登录时返回匿名数据）：

```python
from fastapi.security import SecurityScopes
from app.core.dependencies import get_current_user

@router.get("/public-info")
async def public_info(
    optional_user: User | None = Depends(get_current_user),
):
    """用户可选登录。未登录时 optional_user 为 None。"""
    if optional_user:
        return {"message": f"欢迎回来, {optional_user.username}"}
    return {"message": "请先登录以查看个性化内容"}
```

> 注意：上述 `optional_user` 模式需要额外包装 `get_current_user` 以优雅处理 401，具体实现详见代码中的 `get_optional_current_user()`。

---

## 7. 测试时 Mock 依赖

### 7.1 测试路由依赖

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    """创建测试客户端，注入 mock 依赖。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

# 在 test 中覆盖依赖
async def test_get_farm_status(client):
    # 方法 1: 通过 Cookie 注入 mock session token
    client.cookies.set("session_token", "valid_token_mock")
    
    # 方法 2: 完全覆盖 get_current_user 依赖
    app.dependency_overrides[get_current_user] = lambda: User(id=1, username="test")
    
    response = await client.get("/api/farm/status")
    assert response.status_code == 200
    
    # 清理覆盖
    app.dependency_overrides.clear()
```

### 7.2 测试服务层（无需 FastAPI）

```python
@pytest.mark.asyncio
async def test_auth_service():
    # 直接创建服务实例，传入 mock repo
    mock_repo = Mock(spec=UserRepository)
    mock_repo.get_user_by_id.return_value = User(id=1, username="test")
    
    service = AuthService(mock_repo)
    result = await service.authenticate("test", "password")
    
    assert result is not None
    mock_repo.get_user_by_id.assert_called_once()
```

### 7.3 测试数据库操作

```python
@pytest.fixture
def mock_db_session():
    """创建 mock AsyncSession。"""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session

@pytest.fixture
def test_user_repo(mock_db_session):
    """用 mock session 创建真实 UserRepository。"""
    return UserRepository(mock_db_session)

@pytest.mark.asyncio
async def test_user_repo_get_by_id(test_user_repo):
    mock_user = User(id=1, username="test")
    test_user_repo.db.execute = AsyncMock(return_value=mock_user)
    
    result = await test_user_repo.get_user_by_id(1)
    assert result.username == "test"
```

---

## 附录：文件清单

| 文件 | 职责 |
|------|------|
| `app/core/dependencies.py` | DI 工厂函数实现 |
| `app/core/config.py` | 应用配置（含数据库 URL 等） |
| `app/core/database.py` | `async_session_factory` 定义 |
| `app/core/security.py` | 密码哈希、session token 生成（纯函数） |
| `app/models/user.py` | `User` 模型 |
| `app/repositories/user_repo.py` | `UserRepository` |
| `app/services/auth_service.py` | `AuthService` |

---

*本文档属于 P0 阶段基础设施层文档集。*
