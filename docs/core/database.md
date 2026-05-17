# 数据库模块 (Database)

> 提供 SQLAlchemy 2.0 异步数据库连接、会话管理和模型基类，是所有数据访问层的基石。

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **引擎管理** | 创建并维护全局唯一的异步数据库引擎（Engine） |
| **会话工厂** | 提供异步 Session 工厂（`async_sessionmaker`），供依赖注入使用 |
| **模型基类** | 提供 `DeclarativeBase` 基类，所有 ORM 模型继承它 |
| **初始化入口** | 提供 `init_db()` 函数，在开发阶段自动创建所有表 |
| **配置依赖** | 从 `config.py` 读取 `settings.database_url` 获取连接字符串 |

---

## 2. 设计决策

### 为什么选择 SQLAlchemy 2.0 异步模式？

| 对比项 | SQLAlchemy 2.0 async | SQLAlchemy sync + aiosqlite | Sync + gevent / threadpool |
|--------|---------------------|-----------------------------|----------------------------|
| **与 FastAPI 匹配** | ✅ FastAPI 本身是 async，端到端异步 | ✅ 也支持 | ❌ 阻塞事件循环 |
| **并发性能** | ✅ 非阻塞 I/O，高并发友好 | ✅ 非阻塞 | ❌ 线程切换开销 |
| **连接池** | ✅ 内置 asyncpg/aiomysql 支持 | ✅ 内置 | ❌ 需额外配置 |
| **学习曲线** | ✅ 2.0 统一了 sync/async API | ✅ 基本一致 | ❌ 需理解线程池策略 |
| **SQLite 兼容** | ✅ aiosqlite 完美支持 | ✅ aiosqlite 完美支持 | ✅ 原生支持 |

**结论**：MB Farm 使用 FastAPI（基于 asyncio），端到端异步可避免线程池开销，保持代码简洁且性能最优。即使当前部署在本地局域网、用户量不大，异步模式也为未来扩展预留了空间。

### 核心原则

1. **全局单例引擎** — 引擎在模块加载时创建一次，全应用共享，避免重复连接。
2. **每次请求一个会话** — 通过 FastAPI `Depends` 为每个请求创建独立 Session，请求结束后自动关闭。
3. **DeclarativeBase 基类** — 所有模型继承统一的 Base，`init_db()` 可自动发现所有模型建表。
4. **开发/生产一致** — 开发阶段 `init_db()` 自动建表，生产阶段通过 Alembic 迁移（P1 阶段引入）。

---

## 3. 核心组件

| 组件 | 类型 | 说明 |
|------|------|------|
| `engine` | `AsyncEngine` | 全局异步数据库引擎，管理连接池 |
| `session_factory` | `async_sessionmaker[AsyncSession]` | 异步会话工厂，带 `autocommit=False`, `expire_on_commit=False` |
| `Base` | `DeclarativeBase` | ORM 模型基类，所有 model 继承它 |
| `init_db()` | `Callable[[], Coroutine]` | 自动建表函数（开发阶段用） |
| `get_db()` | `Callable[[], AsyncGenerator]` | 依赖注入用的 Session 提供者 |

---

## 4. 实现方案

### 文件位置

```
mbfarm/
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py      ← 数据库模块
│   │   └── dependencies.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py           ← 继承 Base
│   │   └── ...
│   └── main.py
```

### 完整实现代码

```python
"""app/core/database.py — 数据库基础设施"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# ── 1. 引擎 ──────────────────────────────────────────────
# 全局单例：模块加载时创建一次，全应用共享
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,                    # 开发阶段打印 SQL
    pool_pre_ping=True,                     # 连接存活检测
    pool_recycle=3600,                      # 1 小时回收连接
)


# ── 2. 会话工厂 ──────────────────────────────────────────
# autocommit=False:    不自动提交，需手动 session.commit()
# expire_on_commit=False: 提交后不失效对象属性，方便读取
session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── 3. ORM 基类 ──────────────────────────────────────────
# 所有模型继承 Base，init_db() 可通过 Base.metadata 自动建表
class Base(DeclarativeBase):
    """所有 SQLAlchemy ORM 模型的基类"""
    pass


# ── 4. 初始化数据库（开发阶段用）──────────────────────────
async def init_db() -> None:
    """
    自动创建所有模型对应的表。
    
    使用方式：
        # 在 main.py 启动时调用
        await init_db()
        
    注意：
        - 生产环境应使用 Alembic 进行迁移管理（P1 阶段）
        - 此函数幂等：表已存在则跳过
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── 5. 依赖注入：会话提供者 ──────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入函数，为每个请求创建独立 Session。
    
    使用方式：
        @router.get("/users")
        async def list_users(db: AsyncSession = Depends(get_db)):
            ...
    
    生命周期：
        1. 请求开始 → 创建 Session
        2. 路由处理 → 通过 Depends 注入 db
        3. 请求结束 → yield 后的 finally 块自动关闭 Session
    """
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

---

## 5. 会话生命周期

```
请求进入 FastAPI
       │
       ▼
get_db() 被调用
       │
       ▼
session_factory() 创建 AsyncSession  ←── 从连接池获取连接
       │
       ▼
yield session  ──→ 注入到路由参数
       │
       ▼
路由处理（CRUD 操作）
       │
       ▼
yield 后的 finally 块执行
       │
       ├── 成功 → session.commit()（手动或自动）
       └── 异常 → session.rollback()
       │
       ▼
Session 关闭，连接返回连接池
```

### 关键要点

1. **每次请求一个 Session** — 不会出现跨请求共享会话的问题。
2. **异常自动回滚** — `get_db()` 的 `except` 块捕获异常后自动回滚，防止脏数据。
3. **连接池管理** — SQLAlchemy 内置连接池，连接复用，无需担心频繁创建/销毁连接。
4. **`expire_on_commit=False`** — 提交后对象属性不会被标记为过期，可以安全读取。

---

## 6. 使用方式

### 6.1 在模型中继承 Base

```python
# app/models/user.py
from sqlalchemy import Column, Integer, String
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Integer, default=1)  # 1=active, 0=disabled
    created_at = Column(String(30), nullable=False)  # ISO 8601 字符串
```

### 6.2 在 Repository 中使用 Session

```python
# app/repositories/user_repo.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, username: str, email: str, hashed_password: str) -> User:
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_active=1,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
```

### 6.3 在 Service 中注入 Repository

```python
# app/services/auth_service.py
from app.repositories.user_repo import UserRepository
from app.core.database import AsyncSession


class AuthService:
    def __init__(self, db: AsyncSession):
        self.user_repo = UserRepository(db)

    async def register(self, username: str, email: str, password: str):
        existing = await self.user_repo.get_by_username(username)
        if existing:
            raise ValueError("用户名已存在")
        # ... 注册逻辑
```

### 6.4 在路由中注入 Service

```python
# app/routes/auth.py
from fastapi import APIRouter, Depends, AsyncSession
from app.core.database import get_db
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(
    db: AsyncSession = Depends(get_db),
    service: AuthService = Depends(lambda db: AuthService(db)),
):
    # ... 注册端点
```

---

## 7. 在应用启动时初始化

```python
# app/main.py
from fastapi import FastAPI
from app.core.database import init_db

app = FastAPI(title="MB Farm")


@app.on_event("startup")
async def startup():
    """应用启动时自动建表（开发阶段）"""
    await init_db()


# P1 阶段改为 Alembic 迁移：
# @app.on_event("startup")
# async def startup():
#     await run_migrations()
```

---

## 8. 数据库文件管理

### SQLite 文件位置

```
mbfarm/
├── .env                  ← DATABASE_URL=sqlite:///./mbfarm.db
├── mbfarm.db             ← 数据库文件（加入 .gitignore）
├── app/
│   └── ...
└── data/                 ← 生产环境建议用此目录
    └── mbfarm.db
```

### `.gitignore` 规则

```gitignore
# 数据库文件（SQLite .db 文件）
*.db
*.sqlite
*.sqlite3

# 数据库生成的文件
*.db-journal
*.db-wal
*.db-shm
```

### SQLite URI 格式速查

| 环境 | DATABASE_URL |
|------|-------------|
| 本地开发（当前目录） | `sqlite:///./mbfarm.db` |
| 本地开发（data 子目录） | `sqlite+aiosqlite:///./data/mbfarm.db` |
| 绝对路径 | `sqlite+aiosqlite:////home/liyishan/mbfarm/data/mbfarm.db` |
| PostgreSQL（未来升级） | `postgresql+asyncpg://user:pass@localhost:5432/mbfarm` |
| MySQL（未来升级） | `mysql+aiomysql://user:pass@localhost:3306/mbfarm` |

> **注意**：SQLite 的 SQLAlchemy URI 前缀 `sqlite+aiosqlite://` 可省略，`sqlite:///` 会自动适配 aiosqlite。但显式写出前缀更清晰，便于未来切换数据库。

---

## 9. 连接池配置说明

```python
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,      # 每次获取连接前检测存活
    pool_recycle=3600,       # 连接最大生命周期（秒），防止 SQLite 文件锁定
)
```

| 参数 | 默认值 | MB Farm 值 | 说明 |
|------|--------|-----------|------|
| `pool_size` | 5 | 5 | 连接池大小（SQLite 可保持默认） |
| `max_overflow` | 10 | 10 | 超出 pool_size 后允许的最大溢出连接 |
| `pool_pre_ping` | False | True | 连接存活检测，防止使用已失效连接 |
| `pool_recycle` | -1 | 3600 | 连接回收时间（秒），SQLite 建议设置避免文件锁定 |
| `echo` | False | settings.DEBUG | 是否打印 SQL 语句，开发阶段开启 |

---

## 10. 依赖

```txt
# requirements.txt 中已包含
sqlalchemy>=2.0.0
aiosqlite>=0.19.0
```

**依赖关系图**：

```
database.py
    └── 依赖 config.py (settings.DATABASE_URL)
```

---

## 11. 与 Alembic 的协作（P1 阶段）

P0 阶段使用 `init_db()` 自动建表即可。P1 阶段引入 Alembic 后：

```python
# alembic/env.py 会读取 settings.DATABASE_URL
# 迁移命令：
#   alembic revision --autogenerate -m "initial migration"
#   alembic upgrade head

# app/core/database.py 中的 init_db() 可保留但不调用
# 改为在 main.py 中：
@app.on_event("startup")
async def startup():
    await run_migrations()  # P1: Alembic upgrade head
```

> **关键点**：Alembic 和 `init_db()` 使用同一个 `Base.metadata`，所以无论哪种方式创建的表结构都是兼容的。

---

## 12. 常见陷阱

### 陷阱 1：忘记 `await db.commit()`

```python
# ❌ 错误：只执行了 add，没有 commit
user = User(username="test")
db.add(user)
# 数据不会持久化！

# ✅ 正确：显式提交
db.add(user)
await db.commit()
```

### 陷阱 2：在 Session 关闭后访问对象属性

```python
# ❌ 可能出错：session 关闭后访问 lazy-loaded 关系
async with session_factory() as session:
    user = await session.execute(select(User).where(User.id == 1))
    user = user.scalar_one()
# session 在此关闭

print(user.posts)  # ❌ InvalidRequestError: 会话已关闭

# ✅ 解决：expire_on_commit=False 或显式加载关系
```

### 陷阱 3：SQLite 多写并发

SQLite 不支持高并发写入。MB Farm 用户量少（十几人），单写者场景下没有问题。如果未来需要多进程写入，需迁移到 PostgreSQL。

```python
# 如果未来遇到 SQLite 并发写入问题：
# 1. 迁移到 PostgreSQL（连接字符串替换即可）
# 2. 使用 WAL 模式提升读并发
#   engine = create_async_engine(
#       "sqlite+aiosqlite:///./mbfarm.db",
#       connect_args={"check_same_thread": False, "journal_mode": "WAL"},
#   )
```
