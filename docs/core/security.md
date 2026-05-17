# Security — 安全基础设施

> **模块定位**: `app/core/security.py`
>
> 提供密码哈希和 Session 管理两个核心能力，为认证模块提供底层安全保障。

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **密码哈希** | 对用户密码进行加盐哈希，防止密码明文存储 |
| **Session 管理** | 服务端 Session 的创建、查询、失效和删除 |
| **Token 生成** | 使用 UUID4 生成无状态但可撤销的 Session Token |

---

## 2. 设计决策

### 2.1 密码哈希算法：bcrypt

选用 **bcrypt**（通过 `passlib[bcrypt]` 调用）而非 hashlib 或其他方案的原因：

- **内置 salt**：每次哈希自动随机 salt，无需单独存储 salt 字段
- **工作因子可调**：通过 `rounds` 参数控制哈希强度，未来硬件增强时可递增
- **防御彩虹表**：加盐 + 慢哈希，暴力破解成本高
- **成熟可靠**：bcrypt 是业界标准方案，passlib 提供了简洁的 API

### 2.2 Session 方案：数据库驱动 vs JWT

本项目选择 **Server-side Session（数据库存储）** 而非 JWT，原因：

| 维度 | 数据库 Session | JWT |
|------|-------------|-----|
| **主动登出** | ✅ 直接删除 DB 记录即可 | ❌ Token 有效期内无法吊销 |
| **单设备限制** | ✅ 可限制一个用户同时在线数 | ⚠️ 需额外方案 |
| **过期控制** | ✅ DB 记录可设置 expires_at，定时清理 | ⚠️ 依赖客户端不滥用 |
| **实现复杂度** | 适合十几人的小项目，SQLite 完全够用 | JWT 无状态看似简单，但缺乏服务端控制力 |
| **安全性** | Token 不携带敏感信息，泄露后可删除 | 一旦泄露，在过期前均可用 |

对于 **10-20 人局域网项目**，数据库 Session 方案在安全性和可控性上更优。

---

## 3. 密码哈希

### 3.1 配置

```python
# app/core/security.py
from passlib.context import CryptContext

# bcrypt 算法，work_factor=12（默认值，可根据服务器性能调整）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
```

### 3.2 接口说明

#### `hash_password(plain_password: str) -> str`

将明文密码哈希为 bcrypt 字符串。

- **输入**: 明文密码字符串
- **输出**: bcrypt 哈希字符串（格式: `$2b$12$...`）
- **使用场景**: 用户注册时调用

```python
hashed = hash_password("user_secret_123")
# 返回示例: "$2b$12$KIXwYz8qF3..."
```

#### `verify_password(plain_password: str, hashed_password: str) -> bool`

验证明文密码是否匹配已存储的哈希值。

- **输入**: 明文密码、已存储的 bcrypt 哈希字符串
- **输出**: `True` 匹配成功，`False` 匹配失败
- **使用场景**: 用户登录时调用

```python
match = verify_password("user_secret_123", "$2b$12$KIXwYz8qF3...")
# 返回: True
```

### 3.3 实现代码

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain_password: str) -> str:
    """将明文密码哈希为 bcrypt 字符串。"""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否匹配哈希值。"""
    return pwd_context.verify(plain_password, hashed_password)
```

---

## 4. Session 管理方案

### 4.1 Session 模型设计

Session 数据存储在 SQLite 的 `sessions` 表中：

```python
# app/models/session.py
from sqlalchemy import Column, String, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta, timezone

from app.core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(36), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # 关系
    user = relationship("User", back_populates="sessions")

    def is_expired(self) -> bool:
        """判断 Session 是否已过期。"""
        return datetime.now(timezone.utc) >= self.expires_at
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | VARCHAR(36) | 主键（与 token 值相同，简化查询） |
| `user_id` | BIGINT | 关联用户 ID，外键 |
| `token` | VARCHAR(36) | UUID4 生成的 Session Token，唯一索引 |
| `created_at` | DATETIME | 创建时间 |
| `expires_at` | DATETIME | 过期时间（默认 7 天后） |

### 4.2 Token 生成规则

- 使用 Python 标准库 `uuid.uuid4()` 生成
- 格式：36 字符 UUID 字符串（含连字符），如 `550e8400-e29b-41d4-a716-446655440000`
- 熵值：122 bits，碰撞概率极低
- **不携带任何用户信息**，仅作为查表凭证

```python
import uuid

token = str(uuid.uuid4())
# 返回示例: "550e8400-e29b-41d4-a716-446655440000"
```

### 4.3 接口说明

#### `create_session(user_id: int, expires_in: timedelta = timedelta(days=7)) -> str`

创建新 Session，生成 token 并写入数据库。

- **输入**: 用户 ID、过期时长（默认 7 天）
- **输出**: 生成的 token 字符串
- **返回值**: 可用于设置 Cookie 的 token

```python
from datetime import timedelta
token = create_session(user_id=1, expires_in=timedelta(days=7))
# 返回: "550e8400-e29b-41d4-a716-446655440000"
# DB 中插入记录:
# id="550e8400-...", user_id=1, token="550e8400-...", created_at=..., expires_at=...
```

#### `get_session(token: str) -> Optional[Session]`

根据 token 查询 Session，同时自动清理过期 Session。

- **输入**: Session token 字符串
- **输出**: Session 对象（有效）或 `None`（不存在/已过期）
- **副作用**: 删除已过期但未被清理的 Session 记录

```python
session = get_session("550e8400-e29b-41d4-a716-446655440000")
if session:
    user_id = session.user_id  # Session 有效
else:
    # Token 不存在或已过期
```

#### `delete_session(token: str) -> bool`

删除指定 Session（用于登出操作）。

- **输入**: Session token 字符串
- **输出**: `True` 删除成功，`False` 记录不存在

```python
delete_session("550e8400-e29b-41d4-a716-446655440000")
# DB 中 DELETE FROM sessions WHERE token = ...
```

#### `revoke_all_user_sessions(user_id: int) -> int`

吊销用户所有 Session（用于安全场景，如密码修改、强制下线）。

- **输入**: 用户 ID
- **输出**: 被删除的记录数

```python
count = revoke_all_user_sessions(user_id=1)
# 用户所有登录设备均会被登出
```

### 4.4 实现代码

```python
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session as SQLSession

from app.models.session import Session


def create_session(
    db: SQLSession,
    user_id: int,
    expires_in: timedelta = timedelta(days=7),
) -> str:
    """创建新 Session 并返回 token。"""
    token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + expires_in

    session_record = Session(
        id=token,
        user_id=user_id,
        token=token,
        expires_at=expires_at,
    )
    db.add(session_record)
    db.commit()
    db.refresh(session_record)
    return token


def get_session(db: SQLSession, token: str) -> Optional[Session]:
    """查询 Session，自动清理过期记录。"""
    session_record = db.query(Session).filter(Session.token == token).first()

    if not session_record:
        return None

    if session_record.is_expired():
        # 自动清理过期记录
        db.delete(session_record)
        db.commit()
        return None

    return session_record


def delete_session(db: SQLSession, token: str) -> bool:
    """删除指定 Session。"""
    session_record = db.query(Session).filter(Session.token == token).first()
    if not session_record:
        return False

    db.delete(session_record)
    db.commit()
    return True


def revoke_all_user_sessions(db: SQLSession, user_id: int) -> int:
    """吊销用户所有 Session，返回删除数量。"""
    count = db.query(Session).filter(Session.user_id == user_id).delete()
    db.commit()
    return count
```

---

## 5. Cookie 设置说明

Session Token 通过 HTTP Cookie 传输给客户端，Cookie 设置必须遵循以下安全参数：

### 5.1 推荐 Cookie 参数

```python
from fastapi import Response

def set_session_cookie(response: Response, token: str):
    """设置 Session Cookie。"""
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=604800,           # 7 天（秒），与 Session 过期时间一致
        httponly=True,             # 禁止 JS 读取，防御 XSS
        samesite="lax",           # 防止 CSRF（严格模式下可用 "strict"）
        path="/",                  # 全站有效
        secure=False,              # 本地 HTTP 调试为 False；生产环境用 HTTPS 时设为 True
    )


def clear_session_cookie(response: Response):
    """清除 Session Cookie。"""
    response.delete_cookie(
        key="session_token",
        path="/",
    )
```

### 5.2 参数详解

| 参数 | 值 | 说明 |
|------|-----|------|
| `httponly` | `True` | **禁止 JavaScript 通过 `document.cookie` 读取**，有效防御 XSS 攻击窃取 Session |
| `samesite` | `"lax"` | 防止 CSRF 攻击。`"lax"` 允许顶部导航携带 Cookie，`"strict"` 更严格但不便使用 |
| `secure` | `False`（开发）/ `True`（生产） | 仅在 HTTPS 连接下传输 Cookie。**本地开发使用 HTTP 时设为 False** |
| `max_age` | `604800`（7 天） | Cookie 有效期，与 Session 过期时间一致 |
| `path` | `"/"` | Cookie 全站生效 |

### 5.3 安全提醒

- **生产环境必须使用 HTTPS**，并将 `secure=True`
- 本地开发环境（HTTP）下 `secure=False` 是必要的，否则浏览器不会发送 Cookie
- 如果后续引入 CSRF Token 机制，`samesite` 可保持 `"lax"` 作为额外防护层

---

## 6. 使用方式

### 6.1 在 auth_service 中的调用流程

```python
# app/services/auth_service.py
from sqlalchemy.orm import Session
from app.core.security import hash_password, verify_password
from app.core.security import create_session, get_session, delete_session
from app.schemas.user import UserCreate
from app.models.user import User


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register(self, user_data: UserCreate) -> User:
        """用户注册。"""
        # 1. 检查用户名是否已存在
        existing = self.db.query(User).filter(User.username == user_data.username).first()
        if existing:
            raise ValueError("用户名已存在")

        # 2. 密码哈希
        hashed = hash_password(user_data.password)

        # 3. 创建用户
        new_user = User(
            username=user_data.username,
            hashed_password=hashed,
            nickname=user_data.nickname or user_data.username,
        )
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        return new_user

    def login(self, username: str, password: str, response) -> User:
        """用户登录。"""
        # 1. 查找用户
        user = self.db.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError("用户名或密码错误")

        # 2. 验证密码
        if not verify_password(password, user.hashed_password):
            raise ValueError("用户名或密码错误")

        # 3. 创建 Session
        token = create_session(self.db, user.id)

        # 4. 设置 Cookie
        from app.core.security import set_session_cookie
        set_session_cookie(response, token)

        return user

    def logout(self, token: str) -> bool:
        """用户登出。"""
        from app.core.security import delete_session, clear_session_cookie

        response = None  # 需要依赖注入或通过其他方式获取 Response
        clear_session_cookie(response)
        return delete_session(self.db, token)
```

### 6.2 在路由中的使用

```python
# app/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_session
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate
from app.models.user import User
from app.models.session import Session as SessionModel

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register")
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """用户注册接口。"""
    auth_service = AuthService(db)
    user = auth_service.register(user_data)
    return {"message": "注册成功", "user_id": user.id}


@router.post("/login")
def login(username: str, password: str, response: Response, db: Session = Depends(get_db)):
    """用户登录接口。"""
    auth_service = AuthService(db)
    user = auth_service.login(username, password, response)
    return {"message": "登录成功", "user_id": user.id}


@router.post("/logout")
def logout(response: Response, db: Session = Depends(get_db)):
    """用户登出接口。"""
    token = response.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    auth_service = AuthService(db)
    auth_service.logout(token)
    return {"message": "登出成功"}


def get_current_user(token: str, db: Session = Depends(get_db)) -> User:
    """依赖注入：从 Cookie token 获取当前登录用户。"""
    session = get_session(db, token)
    if not session:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return db.query(User).filter(User.id == session.user_id).first()
```

---

## 7. 依赖关系图

```
routes/auth.py
    │
    ├── AuthService (app/services/auth_service.py)
    │       │
    │       ├── hash_password / verify_password  (app/core/security.py)
    │       ├── create_session / get_session / delete_session  (app/core/security.py)
    │       │
    │       ├── User model       (app/models/user.py)
    │       └── Session model    (app/models/session.py)
    │
    └── get_current_user 依赖 (app/core/security.py)
            │
            └── get_session  (app/core/security.py)
```

---

## 8. 后续扩展

| 功能 | 方案 | 状态 |
|------|------|------|
| **会话并发限制** | 在 `create_session` 中检查同一用户的活跃 Session 数 | 待实现 |
| **登录日志** | 在 `login` 成功后记录 IP、UA 到 logs 表 | 待实现 |
| **强制下线** | 使用 `revoke_all_user_sessions` 实现管理员强制下线 | 待实现 |
| **HTTPS 生产部署** | `secure=True` + HTTPS 反向代理 | 待部署 |
| **CSRF Token** | 表单提交时验证 CSRF Token | 待实现 |
| **密码重置** | 通过邮箱生成 token 重置密码 | 远期规划 |
