# UserRepository & SessionRepository

## 1. 模块职责

`app/repositories/user_repo.py` 是 **Repository 模式** 的数据访问层模块，负责封装所有与用户（User）和会话（Session）相关的数据操作。

核心职责：

- 将 SQLAlchemy 异步查询从业务逻辑（Service）中解耦
- 为 `UserService` 和 `AuthService` 提供统一的 CRUD 接口
- 隐藏数据库查询细节（如 `select()` 语法、`session.execute()`、`session.commit()`）
- 支持依赖注入（每次请求注入新的 `AsyncSession`）

---

## 2. 设计决策

### 2.1 为什么使用 Repository 模式？

| 考虑因素 | 说明 |
|---------|------|
| **解耦** | Service 层不直接依赖 SQLAlchemy 的查询语法，只依赖 Repository 接口 |
| **可测试性** | 在单元测试中可以轻松 mock Repository，无需启动数据库 |
| **可替换性** | 如果未来从 SQLite 迁移到其他数据库，只需修改 Repository 实现 |
| **单一职责** | 数据查询逻辑集中在一个文件中，便于维护和审计 |

### 2.2 为什么 Repository 实例依赖 `AsyncSession`？

Repository **不自己创建或管理 Session**，Session 由 `core/dependencies.py` 中的 `get_db()` 提供。每次 HTTP 请求都会创建一个新的 `AsyncSession`，通过依赖注入传给 Repository：

```
Route → Service → Repository(get_db)
```

这确保了每个请求有独立的数据库会话，避免并发问题。

---

## 3. UserRepository

### 3.1 方法列表

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__` | `db: AsyncSession` | - | 注入数据库会话 |
| `get_by_id` | `user_id: int` | `User \| None` | 根据用户 ID 查询用户 |
| `get_by_username` | `username: str` | `User \| None` | 根据用户名查询用户 |
| `create` | `user_data: dict` | `User` | 创建新用户并返回实例 |
| `update` | `user: User, updates: dict` | `User` | 更新用户字段 |

### 3.2 方法详情

#### `get_by_id(user_id: int) → User | None`

根据主键查询用户。如果用户不存在则返回 `None`。

```python
stmt = select(User).where(User.id == user_id)
result = await self.db.execute(stmt)
return result.scalar_one_or_none()
```

#### `get_by_username(username: str) → User | None`

根据用户名查询用户（用户名是唯一索引）。用于注册时查重和登录时查找。

```python
stmt = select(User).where(User.username == username)
result = await self.db.execute(stmt)
return result.scalar_one_or_none()
```

#### `create(user_data: dict) → User`

从字典创建新用户：

1. 使用 `**user_data` 展开到 `User()` 构造函数
2. `db.add(user)` 加入会话
3. `db.commit()` + `db.refresh(user)` 持久化并刷新
4. 返回用户实例

```python
user = User(**user_data)
self.db.add(user)
await self.db.commit()
await self.db.refresh(user)
return user
```

#### `update(user: User, updates: dict) → User`

更新用户的指定字段：

1. 遍历 `updates` 字典，使用 `setattr()` 设置字段
2. `db.commit()` + `db.refresh(user)` 持久化

```python
for key, value in updates.items():
    setattr(user, key, value)
await self.db.commit()
await self.db.refresh(user)
return user
```

---

## 4. SessionRepository

### 4.1 方法列表

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__` | `db: AsyncSession` | - | 注入数据库会话 |
| `get_by_token` | `token: str` | `Session \| None` | 根据 token 查询会话 |
| `create` | `user_id: int, token: str, expires_at: datetime` | `Session` | 创建新会话 |
| `delete` | `session: Session` | - | 删除指定会话 |
| `delete_all_by_user_id` | `user_id: int` | - | 删除用户的所有会话（退出登录时用） |

### 4.2 方法详情

#### `get_by_token(token: str) → Session | None`

根据会话 token 查找有效会话。用于认证中间件验证用户登录状态。

```python
stmt = select(Session).where(Session.token == token)
result = await self.db.execute(stmt)
return result.scalar_one_or_none()
```

#### `create(user_id: int, token: str, expires_at: datetime) → Session`

创建新会话记录：

```python
session = Session(user_id=user_id, token=token, expires_at=expires_at)
self.db.add(session)
await self.db.commit()
await self.db.refresh(session)
return session
```

#### `delete(session: Session)`

删除单个会话（用户主动退出时）：

```python
await self.db.delete(session)
await self.db.commit()
```

#### `delete_all_by_user_id(user_id: int)`

删除用户的所有会话（账号切换/强制退出时）：

```python
stmt = delete(Session).where(Session.user_id == user_id)
await self.db.execute(stmt)
await self.db.commit()
```

---

## 5. 完整实现代码

```python
"""
UserRepository & SessionRepository

Repository 模式的数据访问层，封装 User 和 Session 的 CRUD 操作。
每个 Repository 实例依赖一个 AsyncSession，由 FastAPI 依赖注入提供。
"""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Session, User


class UserRepository:
    """用户数据访问层"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        """根据用户 ID 查询用户"""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """根据用户名查询用户"""
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user_data: dict) -> User:
        """创建新用户"""
        user = User(**user_data)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user: User, updates: dict) -> User:
        """更新用户指定字段"""
        for key, value in updates.items():
            setattr(user, key, value)
        await self.db.commit()
        await self.db.refresh(user)
        return user


class SessionRepository:
    """会话数据访问层"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_token(self, token: str) -> Session | None:
        """根据 token 查询会话"""
        stmt = select(Session).where(Session.token == token)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user_id: int, token: str, expires_at: datetime) -> Session:
        """创建新会话"""
        session = Session(user_id=user_id, token=token, expires_at=expires_at)
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def delete(self, session: Session) -> None:
        """删除指定会话"""
        await self.db.delete(session)
        await self.db.commit()

    async def delete_all_by_user_id(self, user_id: int) -> None:
        """删除用户的所有会话（强制退出）"""
        stmt = delete(Session).where(Session.user_id == user_id)
        await self.db.execute(stmt)
        await self.db.commit()
```

---

## 6. 与 Services 层的集成

### 6.1 依赖注入流程

Repository 通过 FastAPI 的依赖注入系统获取 `AsyncSession`，Service 层再注入 Repository：

```
┌─────────────────────────────────────────────────────────┐
│  Routes (api/routes/auth.py)                            │
│  - 调用 AuthService.register() / login()                │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  Services (app/services/auth_service.py)                │
│  - 依赖注入 UserRepository, SessionRepository           │
│  - 调用 repo.get_by_username(), repo.create() 等        │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  Repositories (app/repositories/user_repo.py)           │
│  - 依赖注入 AsyncSession (from get_db)                  │
│  - 执行 SQLAlchemy 查询                                 │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  Database (app/core/database.py)                        │
│  - get_db() → AsyncSession generator                    │
└─────────────────────────────────────────────────────────┘
```

### 6.2 在 Service 中使用示例

```python
# app/services/auth_service.py
from app.repositories.user_repo import UserRepository, SessionRepository

class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
    ):
        self.user_repo = user_repo
        self.session_repo = session_repo

    async def register(self, username: str, password: str) -> User:
        existing = await self.user_repo.get_by_username(username)
        if existing:
            raise ValueError("用户名已存在")
        hashed = hash_password(password)
        user = await self.user_repo.create({
            "username": username,
            "hashed_password": hashed,
        })
        return user

    async def login(self, username: str, password: str) -> Session:
        user = await self.user_repo.get_by_username(username)
        if not user or not verify_password(password, user.hashed_password):
            raise ValueError("用户名或密码错误")
        token = generate_token()
        expires_at = datetime.utcnow() + timedelta(days=7)
        # 清除该用户的所有旧会话
        await self.session_repo.delete_all_by_user_id(user.id)
        session = await self.session_repo.create(user.id, token, expires_at)
        return session
```

### 6.3 在 Route 中注入

```python
# app/core/dependencies.py
from functools import lru_cache

@lru_cache
def get_repositories():
    """Route 层注入 Repository 实例"""
    # 实际使用时会从 get_db() 获取 session 并传给 Repository
    pass
```

---

## 7. 扩展说明

### 7.1 未来可添加的方法

- `UserRepository.get_all(page, page_size)` — 分页查询用户列表
- `UserRepository.delete(user_id)` — 删除用户
- `SessionRepository.cleanup_expired()` — 清理过期会话（定时任务）
- `SessionRepository.get_active_sessions(user_id)` — 获取用户当前有效会话列表

### 7.2 事务边界

所有 `create` / `update` / `delete` 方法内部执行 `commit()`，确保操作原子性。由于每个 Repository 实例对应单个请求的 Session，不会出现跨请求的事务问题。
