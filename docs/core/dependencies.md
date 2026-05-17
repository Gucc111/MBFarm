# 依赖注入 (DI) 基础设施模块

> 模块定位：`app/core/dependencies.py`
> 本文档描述该模块的设计、接口与使用方式。

---

## 1. 模块职责

本模块提供 **FastAPI 依赖注入工厂函数**，将基础设施组件（数据库会话、用户仓库、认证服务等）以声明式方式注入到 API 路由和业务逻辑中。

核心职责：

- 提供当前认证用户的解析逻辑（从 Cookie session token → `User` 实例）
- 提供 Repository 和 Service 的工厂函数

---

## 2. 设计决策

### 2.1 构造函数注入 + FastAPI `Depends`

MB Farm 采用 **构造函数注入**（业务服务层） + **FastAPI `Depends`**（框架层绑定），两者互补：

- **框架层**（Routes → Depends）：FastAPI 在请求生命周期中自动创建、传递、清理依赖。
- **业务层**（Services → 构造函数）：服务实例在请求时通过工厂函数创建，依赖通过构造函数传入。

### 2.2 路由层的 `_get_service` 模式

在 `routes/auth.py` 中，使用内联 `_get_service(db)` 工厂函数创建 `AuthService` 实例：

```python
def _get_service(db: AsyncSession) -> AuthService:
    return AuthService(db, UserRepository(db), SessionRepository(db))
```

此模式确保同一个 `db` 会话被传递给 Service 和两个 Repository，避免多会话问题。`dependencies.py` 中的 `get_auth_service` 也可独立使用，但当前路由选择内联方式以获得更清晰的事务边界。

---

## 3. DI 工厂函数列表

### 3.1 `get_db() → AsyncSession`

定义在 `app/core/database.py` 中，请求级 AsyncSession 工厂。

- **返回类型**：`AsyncSession`
- **生命周期**：单个 HTTP 请求
- **清理**：请求结束时自动 `close()`
- **异常处理**：出错时自动 `rollback()` 并重新抛出

### 3.2 `get_current_user() → User`

从 Cookie 中的 `session_token` 解析当前认证用户。

```python
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias="session_token"),
) -> User:
    """从 Cookie session_token 验证并返回当前用户。"""
    if not session_token:
        raise HTTPException(status_code=401, detail="未提供认证信息")

    session_repo = SessionRepository(db)
    session = await session_repo.get_by_token(session_token)
    if not session or session.is_expired():
        raise HTTPException(status_code=401, detail="会话已过期或无效")

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    return user
```

### 3.3 `get_user_repo(db: AsyncSession) → UserRepository`

工厂函数：创建用户仓库实例，注入数据库会话。

### 3.4 `get_session_repo(db: AsyncSession) → SessionRepository`

工厂函数：创建会话仓库实例，注入数据库会话。

### 3.5 `get_auth_service(...) → AuthService`

工厂函数：创建认证服务实例，注入 db、user_repo 和 session_repo。

---

## 4. 依赖链

```
HTTP Request
    │
    ▼
API Route (e.g. /api/auth/me)
    │
    ├── Depends(get_db) → AsyncSession
    │
    ├── Cookie(session_token) → str
    │
    └── _get_service(db) → AuthService(db, UserRepository(db), SessionRepository(db))
            │
            ├── UserRepository(db) → async SQL queries
            └── SessionRepository(db) → async SQL queries
```

---

## 5. 使用方式

### 5.1 路由中使用 get_current_user

```python
@router.get("/protected")
async def protected(user: User = Depends(get_current_user)):
    return {"username": user.username}
```

### 5.2 路由中使用 _get_service 模式（当前 auth.py 采用）

```python
def _get_service(db: AsyncSession) -> AuthService:
    return AuthService(db, UserRepository(db), SessionRepository(db))

@router.post("/register")
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    service = _get_service(db)
    user = await service.register(user_data.username, user_data.password)
    return user
```

### 5.3 路由中使用 get_auth_service（替代方案）

```python
@router.post("/login")
async def login(
    login_data: UserLogin,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    ...
```

> 注意：使用 `get_auth_service` 时会为每个 Depends 调用创建独立的 `get_db` 会话。当前代码中 `routes/auth.py` 选择 `_get_service(db)` 内联模式以确保所有操作共享同一 Session。

---

## 6. 附录：文件清单

| 文件 | 职责 |
|------|------|
| `app/core/dependencies.py` | DI 工厂函数实现 |
| `app/core/database.py` | `get_db()` 定义 |
| `app/core/security.py` | 密码哈希、cookie 辅助函数 |
| `app/models/user.py` | `User` 模型 |
| `app/models/session.py` | `Session` 模型 |
| `app/repositories/user_repo.py` | `UserRepository` + `SessionRepository` |
| `app/services/auth_service.py` | `AuthService` |
