# User & Session — 数据模型

> **模块定位**: `app/models/user.py`（User）、`app/models/session.py`（Session）
>
> 定义 P0 阶段涉及的两个核心 SQLAlchemy 模型：`User`（用户）和 `Session`（会话）。

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **User 模型** | 存储用户基本信息（用户名、密码哈希、金币、体力、经验值、等级） |
| **Session 模型** | 存储服务端 Session 记录，支持 Token 查询、过期判断、主动吊销 |
| **外键关系** | Session → User 一对多外键约束，级联删除 |

---

## 2. 模型设计

### 2.1 User 模型

存储用户账户信息和游戏状态。所有字段均在注册时确定初始值，后续通过业务逻辑更新。

```sql
CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        VARCHAR(32) UNIQUE NOT NULL,
    password_hash   VARCHAR(128) NOT NULL,
    coins           INTEGER DEFAULT 500 NOT NULL,
    stamina         INTEGER DEFAULT 100 NOT NULL,
    xp              INTEGER DEFAULT 0 NOT NULL,
    level           INTEGER DEFAULT 1 NOT NULL,
    last_active_at  DATETIME,
    created_at      DATETIME DEFAULT (datetime('now', 'utc')),

    CHECK(stamina >= 0)
);
```

**字段说明**:

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | — | 自增主键 |
| `username` | VARCHAR(32) | UNIQUE, NOT NULL | — | 用户名，32 字符内唯一 |
| `password_hash` | VARCHAR(128) | NOT NULL | — | bcrypt 哈希值（不含明文密码） |
| `coins` | INTEGER | NOT NULL | 500 | 金币余额，新手初始 500 |
| `stamina` | INTEGER | NOT NULL, CHECK >= 0 | 100 | 当前体力，上限由 `core/constants.py` 的 `STAMINA.max_value` 定义 |
| `xp` | INTEGER | NOT NULL | 0 | 经验值，种植/收获时增加 |
| `level` | INTEGER | NOT NULL | 1 | 等级，由 XP 查表得出（`core/constants.py` LEVEL_XP_THRESHOLD） |
| `last_active_at` | DATETIME | 可空 | NULL | 最后活跃时间，用于计算离线体力恢复 |
| `created_at` | DATETIME | NOT NULL | 当前 UTC 时间 | 注册时间 |

**设计理由**:

- **stamina 存 User 表**：体力是用户核心资源，每次请求都需要读取和更新，存在用户表上避免额外 JOIN。
- **last_active_at 存 User 表**：每次请求更新此字段，用于 `game_engine.restore_stamina()` 计算离线体力恢复。
- **CHECK(stamina >= 0)**：数据库层面保证体力不为负数，防止 bug 导致异常状态。
- **不存 nickname 独立字段**：初期 nickname 与 username 相同，后续可通过 `username` 派生。
- **coins/xp/level 分开存储**：虽然 level 可由 xp 计算，但分开存储避免每次查询都计算。
- **VARCHAR(128) 而非 VARCHAR(60)**：bcrypt 哈希长度可能超过 60 字符，128 是安全上限。

### 2.2 Session 模型

存储服务端 Session 记录，用于认证状态管理。

```sql
CREATE TABLE sessions (
    id         VARCHAR(36) PRIMARY KEY,
    user_id    BIGINT NOT NULL,
    token      VARCHAR(36) UNIQUE NOT NULL,
    created_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(token);
```

**字段说明**:

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | VARCHAR(36) | PRIMARY KEY | 与 `token` 值相同，简化查询（id == token） |
| `user_id` | BIGINT | NOT NULL, FK → users.id, INDEX | 关联用户 ID |
| `token` | VARCHAR(36) | UNIQUE, NOT NULL, INDEX | UUID4 生成的 Session Token |
| `created_at` | DATETIME | NOT NULL | 创建时间 |
| `expires_at` | DATETIME | NOT NULL | 过期时间 |

**设计理由**:

- **id == token**：UUID4 本身熵值高、唯一性有保证，直接复用为 id 和 token。
- **BIGINT 而非 INTEGER**：跨数据库迁移时更安全。
- **ON DELETE CASCADE**：用户删除时自动清理其所有 Session 记录。
- **双索引**：user_id 和 token 都有索引，加速查询。

---

## 3. 实现代码

### 3.1 User 模型

```python
# app/models/user.py
from typing import Optional

from datetime import datetime, timezone
from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    # 字段
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(32), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    coins = Column(Integer, default=500, nullable=False)
    stamina = Column(Integer, default=100, nullable=False)
    xp = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=1, nullable=False)
    last_active_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("stamina >= 0", name="chk_stamina_non_negative"),
    )

    # 关系
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
```

### 3.2 Session 模型

```python
# app/models/session.py
import uuid
from typing import Optional

from datetime import datetime, timedelta, timezone
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    # 字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(36), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # 关系
    user = relationship("User", back_populates="sessions")

    # 方法
    def is_expired(self) -> bool:
        """判断 Session 是否已过期。"""
        return datetime.now(timezone.utc) >= self.expires_at

    def remaining_seconds(self) -> int:
        """返回 Session 剩余有效秒数。"""
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))
```

### 3.3 模型关系说明

```
User (1) ────< Session (*)
  │                  │
  │                  └─ user_id → users.id (ON DELETE CASCADE)
  │
  └─ sessions 关系（一对多，级联删除孤儿记录）
```

- **User → Session**: `back_populates="user"`，通过 `user.sessions` 可获取该用户的所有 Session。
- **Session → User**: `back_populates="sessions"`，通过 `session.user` 可获取所属用户。
- **级联删除**: `CASCADE` 确保删除用户时自动清理其 Session 记录。

---

## 4. 与 SQLAlchemy 的集成

### 4.1 DeclarativeBase

两个模型均继承自 `app.core.database.Base`，该基类在 `database.py` 中定义：

```python
# app/core/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

class Base(DeclarativeBase):
    pass
```

### 4.2 异步会话兼容

SQLAlchemy 2.0 的 DeclarativeBase 模型与异步会话（`AsyncSession`）完全兼容：

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### 4.3 模型创建

开发环境：

```python
from app.core.database import Base, engine

def init_db():
    """创建所有注册的表（开发环境使用）。"""
    Base.metadata.create_all(bind=engine)
```

生产环境推荐使用 Alembic 进行迁移管理。

---

## 5. 使用示例

### 5.1 创建用户

```python
async def create_user(db: AsyncSession, username: str, password_hash: str) -> User:
    user = User(
        username=username,
        password_hash=password_hash,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user
```

### 5.2 更新用户最后活跃时间

```python
async def update_last_active(db: AsyncSession, user: User):
    user.last_active_at = datetime.now(timezone.utc)
    await db.flush()
```

### 5.3 计算离线体力恢复

```python
from app.services.game_engine import restore_stamina
from app.core.constants import STAMINA

async def calc_stamina(user: User) -> int:
    if user.last_active_at is None:
        return user.stamina
    new_stamina = restore_stamina(
        current_stamina=user.stamina,
        last_active=user.last_active_at,
        max_stamina=STAMINA.max_value,
        restore_per_minute=STAMINA.restore_per_minute,
    )
    return min(new_stamina, STAMINA.max_value)
```

---

## 6. 后续扩展

| 功能 | 方案 | 状态 |
|------|------|------|
| **nickname 独立字段** | 添加 `nickname` 字段 | 远期 |
| **头像 URL** | 添加 `avatar_url` 字段 | 远期 |
| **Session 并发限制** | 检查同一用户活跃 Session 数 | 待实现 |
| **用户状态字段** | 添加 `is_active` 支持账号禁用 | 待实现 |
| **软删除** | 添加 `deleted_at` 字段 | 远期 |
