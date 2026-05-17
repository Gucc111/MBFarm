# Security — 安全基础设施

> **模块定位**: `app/core/security.py`
>
> 提供密码哈希、Session Token 生成和 Cookie 管理三个核心能力，为认证模块提供底层安全保障。
> Session 数据的 CRUD 操作由 `SessionRepository` 负责（`app/repositories/user_repo.py`）。

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **密码哈希** | 对用户密码进行加盐哈希，防止密码明文存储 |
| **Token 生成** | 使用 UUID4 生成无状态但可撤销的 Session Token |
| **Cookie 管理** | 设置和清除 Session Cookie 的辅助函数 |

> **注意**：Session 数据库记录的生命周期（创建、查询、删除、吊销）由 `SessionRepository` 负责，不属于本模块职责。

---

## 2. 设计决策

### 2.1 密码哈希算法：bcrypt

选用 **bcrypt**（通过 `passlib[bcrypt]` 调用）而非 hashlib 或其他方案的原因：

- **内置 salt**：每次哈希自动随机 salt，无需单独存储 salt 字段
- **工作因子可调**：通过 `rounds` 参数控制哈希强度
- **防御彩虹表**：加盐 + 慢哈希，暴力破解成本高
- **成熟可靠**：bcrypt 是业界标准方案

### 2.2 Session 方案：数据库驱动

本项目选择 **Server-side Session（数据库存储）** 而非 JWT。
Session Token 为 UUID4 字符串，不携带任何用户信息，仅作为查表凭证。
Session 记录的增删改查由 `SessionRepository` 处理。

### 2.3 Token 生成规则

- 使用 Python 标准库 `uuid.uuid4()` 生成
- 格式：36 字符 UUID 字符串（含连字符）
- 熵值：122 bits，碰撞概率极低
- **不携带任何用户信息**，仅作为查表凭证

---

## 3. 密码哈希

### 3.1 配置

```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
```

### 3.2 接口

#### `hash_password(plain_password: str) -> str`

将明文密码哈希为 bcrypt 字符串。用于用户注册时。

#### `verify_password(plain_password: str, hashed_password: str) -> bool`

验证明文密码是否匹配已存储的哈希值。用于用户登录时。

---

## 4. Session Token 生成

#### `generate_session_token() -> str`

返回一个随机 UUID4 字符串。实际登录时 `AuthService.login()` 直接调用 `str(uuid.uuid4())` 生成 token。

---

## 5. Cookie 辅助函数

#### `set_session_cookie(response: Response, token: str, expires_days: int = 7) -> None`

设置 HttpOnly Session Cookie。

#### `clear_session_cookie(response: Response) -> None`

清除 Session Cookie。

### 推荐 Cookie 参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `httponly` | `True` | 禁止 JS 读取，防御 XSS |
| `samesite` | `"lax"` | 防止 CSRF |
| `secure` | `False`（开发）/ `True`（生产） | 仅 HTTPS 传输 |
| `max_age` | `604800`（7 天） | Cookie 有效期 |
| `path` | `"/"` | 全站生效 |

---

## 6. Session 数据管理

Session 数据库记录（创建、查询、删除）由以下模块负责：

| 操作 | 模块 | 位置 |
|------|------|------|
| 创建 Session | `SessionRepository.create()` | `app/repositories/user_repo.py` |
| 查询 Session | `SessionRepository.get_by_token()` | `app/repositories/user_repo.py` |
| 删除 Session | `SessionRepository.delete()` | `app/repositories/user_repo.py` |
| 吊销所有 Session | `SessionRepository.delete_all_by_user_id()` | `app/repositories/user_repo.py` |

---

## 7. 使用方式

### 在 auth_service 中的调用流程

```python
# app/services/auth_service.py
from app.core.security import hash_password, verify_password

class AuthService:
    async def register(self, username: str, password: str) -> User:
        hashed = hash_password(password)
        user = await self.user_repo.create({"username": username, "password_hash": hashed})
        return user

    async def login(self, username: str, password: str) -> Session:
        user = await self.user_repo.get_by_username(username)
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("用户名或密码错误")
        # token 生成和 session 创建由 AuthService 和 SessionRepository 协作完成
```

### 在路由中的 Cookie 使用

```python
from app.core.security import set_session_cookie, clear_session_cookie

@router.post("/login")
async def login(login_data: UserLogin, response: Response, ...):
    session = await service.login(...)
    set_session_cookie(response, session.token)  # 设置 Cookie
    return LoginResponse(...)

@router.post("/logout")
async def logout(response: Response, ...):
    clear_session_cookie(resp)  # 清除 Cookie
    return {"message": "已登出"}
```

---

## 8. 依赖关系图

```
routes/auth.py
    │
    ├── AuthService (app/services/auth_service.py)
    │       │
    │       ├── hash_password / verify_password  (app/core/security.py)
    │       │
    │       ├── SessionRepository (app/repositories/user_repo.py)
    │       │       └── Session model (app/models/session.py)
    │       │
    │       └── UserRepository (app/repositories/user_repo.py)
    │               └── User model (app/models/user.py)
    │
    └── set_session_cookie / clear_session_cookie (app/core/security.py)
```

---

## 9. 安全提醒

- **生产环境必须使用 HTTPS**，并将 `secure=True`
- 本地开发环境（HTTP）下 `secure=False` 是必要的
- `SECRET_KEY` 配置项在 `.env` 中设置，生产环境必须修改

---

## 10. 后续扩展

| 功能 | 方案 | 状态 |
|------|------|------|
| **会话并发限制** | 在 `create_session` 中检查同一用户的活跃 Session 数 | 待实现 |
| **登录日志** | 在 `login` 成功后记录 IP、UA 到 logs 表 | 待实现 |
| **强制下线** | 使用 `delete_all_by_user_sessions` 实现管理员强制下线 | 待实现 |
