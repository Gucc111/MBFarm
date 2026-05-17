# core.exceptions — 业务异常与全局异常处理

## 1. 模块职责

在 `core/exceptions.py` 中统一定义 MB Farm 的全部业务异常类，并提供一套全局异常处理器，使所有异常在到达 HTTP 层时都能被**捕获 → 转换 → 返回统一格式的 JSON 错误响应**。

核心职责：
- 定义层次化的业务异常类（`AppError` 及其子类）
- 为每个异常绑定默认 HTTP 状态码
- 提供统一的 `error_code` 枚举，便于前端 / 日志排查
- 在 `main.py` 中注册全局异常处理器（`ExceptionHandler`）

---

## 2. 设计决策

### 为什么不用 `HTTPException`？

| 维度 | `HTTPException` | 自定义 `AppError` |
|---|---|---|
| 语义清晰度 | `status_code=409` 含义不够直白 | `ConflictError("用户名已存在")` 一目了然 |
| 扩展性 | 只有 `status_code` + `detail` | 可携带 `error_code`、`extra` 等额外字段 |
| 分层解耦 | Service 层依赖 FastAPI 类型，耦合框架 | Service 层只依赖业务异常，与 HTTP 层无关 |
| 错误码管理 | 无内置错误码概念 | `ErrorCode` 枚举统一管理，便于国际化 / 日志统计 |

**结论**：Service / Repository 层统一抛出 `AppError` 子类；仅在 `main.py` 的全局异常处理器中将 `AppError` 映射为 `JSONResponse`。

### 与 Pydantic `ValidationError` 的关系

Pydantic 的 `ValidationError`（422）由 FastAPI 自动处理，**不属于业务异常**。本项目保留 FastAPI 默认的 422 行为（返回详细校验错误），不与 `AppError` 冲突。

---

## 3. 异常类列表

| 异常类 | HTTP 状态码 | error_code | 使用场景 |
|---|---|---|---|
| `AppError` | 500（基类默认） | `INTERNAL_ERROR` | 未分类的通用服务器错误 |
| `UnauthorizedError` | 401 | `UNAUTHORIZED` | 未登录、Token 过期、密码错误 |
| `NotFoundError` | 404 | `NOT_FOUND` | 资源不存在（用户、作物、地块等） |
| `ConflictError` | 409 | `CONFLICT` | 用户名已注册、重复提交等 |
| `ValidationError` | 422 | `VALIDATION_ERROR` | 业务规则校验失败（非 Pydantic） |
| `ForbiddenError` | 403 | `FORBIDDEN` | 权限不足（如偷别人菜时防御机制触发） |

### `AppError`（基类）

```
class AppError(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "An unexpected error occurred", extra: dict | None = None):
        self.message = message
        self.extra = extra or {}
```

所有子类通过类属性覆盖 `status_code` 和 `error_code`。

---

## 4. 全局异常处理器

在 `main.py` 中注册一个基于 `AppError` 的全局异常处理器：

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core.exceptions import AppError

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                **(exc.extra or {}),
            }
        },
    )
```

对于其他特定异常（如 `RequestValidationError`），保留 FastAPI 默认行为或单独注册处理器。

---

## 5. 错误响应格式

所有业务异常返回统一的 JSON 结构：

```json
{
  "error": {
    "code": "CONFLICT",
    "message": "用户名已存在"
  }
}
```

当携带 `extra` 数据时：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "操作失败",
    "fields": {
      "username": ["用户名长度必须在 3-20 之间"]
    }
  }
}
```

**约定**：
- `error.code` 为大写蛇形命名，全局唯一
- `error.message` 为面向用户的中文描述
- `extra` 字段仅在需要额外调试信息时出现

---

## 6. 实现方案

### 6.1 `ErrorCode` 枚举（可选）

为每个错误码提供枚举值，方便类型检查和日志统计：

```python
from enum import StrEnum

class ErrorCode(StrEnum):
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    FORBIDDEN = "FORBIDDEN"
```

### 6.2 异常类完整定义

```python
from enum import StrEnum
from typing import Any

class ErrorCode(StrEnum):
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    FORBIDDEN = "FORBIDDEN"


class AppError(Exception):
    status_code: int = 500
    error_code: str = ErrorCode.INTERNAL_ERROR

    def __init__(self, message: str = "An unexpected error occurred", extra: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.extra = extra or {}


class UnauthorizedError(AppError):
    status_code = 401
    error_code = ErrorCode.UNAUTHORIZED


class NotFoundError(AppError):
    status_code = 404
    error_code = ErrorCode.NOT_FOUND


class ConflictError(AppError):
    status_code = 409
    error_code = ErrorCode.CONFLICT


class AppValidationError(AppError):
    status_code = 422
    error_code = ErrorCode.VALIDATION_ERROR


class ForbiddenError(AppError):
    status_code = 403
    error_code = ErrorCode.FORBIDDEN
```

---

## 7. 使用方式

### 7.1 Service 层抛出异常

```python
# app/services/auth_service.py
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError

class AuthService:
    async def register(self, username: str, password: str) -> User:
        existing = await self.user_repo.get_by_username(username)
        if existing:
            raise ConflictError("用户名已存在")

        user = await self.user_repo.create(username, self.hash_password(password))
        return user

    async def login(self, username: str, password: str) -> str:
        user = await self.user_repo.get_by_username(username)
        if not user:
            raise NotFoundError("用户不存在")
        if not self.verify_password(password, user.password_hash):
            raise UnauthorizedError("密码错误")

        token = self.generate_token(user.id)
        return token
```

### 7.2 Route 层不捕获，交由全局处理器

```python
# app/api/routes/auth.py
from fastapi import APIRouter
from app.services.auth_service import AuthService

router = APIRouter()

@router.post("/register")
async def register(body: UserCreate):
    service = AuthService()
    user = await service.register(body.username, body.password)
    return {"message": "注册成功", "user_id": user.id}
    # ConflictError 会自动被转为 409 JSONResponse
```

**不要**在 route 层手动 `try/except` 业务异常——全局处理器统一接管。

### 7.3 何时手动捕获

仅在需要**优雅降级**或**补充上下文**时手动捕获：

```python
@router.post("/register")
async def register(body: UserCreate):
    try:
        user = await service.register(body.username, body.password)
    except ConflictError as e:
        # 记录额外日志后再重新抛出（或直接返回自定义响应）
        logger.warning(f"重复注册: {body.username}, extra={e.extra}")
        raise
    return user
```

---

## 8. 文件位置

```
app/
├── core/
│   ├── __init__.py
│   ├── exceptions.py       # ← 异常类定义
├── main.py                 # ← 全局异常处理器注册
└── services/
    └── auth_service.py     # ← Service 层抛出异常
```

---

## 9. 注意事项

1. **不要在 repository 层抛出 `AppError`**——repository 应只抛底层异常（如 `IntegrityError`），由 service 层捕获并转为业务异常。
2. **500 不应暴露给用户**——`AppError` 默认 500 仅用于开发阶段；生产环境应在全局处理器中兜底，返回通用错误消息。
3. **与 Pydantic 校验的边界**——Pydantic 校验失败（字段缺失、类型错误）由 FastAPI 自动返回 422，不需要手动抛 `AppValidationError`。`AppValidationError` 仅用于**业务规则校验**。
4. **日志记录**——建议在全局异常处理器中记录 `exc.message` + `exc.extra` 到日志，便于排查。
