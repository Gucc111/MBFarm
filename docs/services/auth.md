# 认证服务 (app/services/auth_service.py)

## 职责

- 封装用户认证业务逻辑（注册、登录、会话验证、登出）。
- 协调 `UserRepository` 和 `SessionRepository`。
- 使用 `INIT_USER` 常量初始化新用户属性。

## 类签名

```python
class AuthService:
    def __init__(self, db: AsyncSession, user_repo: UserRepository, session_repo: SessionRepository):
        ...
```

## 方法

### `register(username, password) -> User`

1. 检查用户名是否已存在（`user_repo.get_by_username`）。
2. 哈希密码（`hash_password`）。
3. 创建用户，使用 `INIT_USER` 常量初始化初始属性：
   ```python
   user = await self.user_repo.create({
       "username": username,
       "password_hash": password_hash,
       "coins": INIT_USER.gold,
       "stamina": INIT_USER.stamina,
       "xp": INIT_USER.xp,
       "level": INIT_USER.level,
   })
   ```
4. 返回创建的 User 对象。

### `login(username, password) -> SessionModel`

1. 查询用户（`user_repo.get_by_username`）。
2. 验证密码（`verify_password`）。
3. 清理该用户的所有旧 Session（单设备限制，`session_repo.delete_all_by_user_id`）。
4. 生成 UUID4 Token，创建 Session 记录（7 天过期）。
5. 返回 Session 对象。

### `logout(session: SessionModel) -> None`

1. 删除 Session 记录（`session_repo.delete`）。

### `get_current_user(session_token: str) -> User`

1. 通过 Token 查询 Session（`session_repo.get_by_token`）。
2. 检查会话是否过期（`session.is_expired()`）。
3. 通过 `session.user_id` 查询 User。
4. 返回 User 对象。

## 异常处理

所有方法在异常情况下抛出 `core/exceptions` 模块中的业务异常（`ConflictError`, `NotFoundError`, `UnauthorizedError`, `AppValidationError`），由 `main.py` 全局异常处理器统一转换为 JSON 响应。路由层不手动 try/except。
