# Middleware: Rate Limit

## 模块职责

全局 API 限流中间件，保护 API 不被滥用。支持基于 IP 和基于用户的限流。

---

## 限流策略

| 端点类别 | 限流规则 | 窗口 |
|---|---|---|
| 认证（登录/注册） | 5 次/分钟 | 1 分钟 |
| 偷菜 | 10 次/分钟 | 1 分钟 |
| 种植/收获 | 30 次/分钟 | 1 分钟 |
| 其他 GET | 60 次/分钟 | 1 分钟 |
| 其他 POST/PUT/DELETE | 20 次/分钟 | 1 分钟 |

---

## 完整中间件代码

```python
"""app/middleware/rate_limit.py — Rate limiting middleware."""

from __future__ import annotations

import time
import logging
from collections import defaultdict
from typing import Optional

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitEntry:
    """单个限流条目。"""

    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window  # 秒
        self.requests: list[float] = []

    def is_allowed(self) -> bool:
        """检查是否允许请求。"""
        now = time.time()
        # 清理过期记录
        self.requests = [t for t in self.requests if now - t < self.window]
        if len(self.requests) >= self.limit:
            return False
        self.requests.append(now)
        return True

    @property
    def remaining(self) -> int:
        now = time.time()
        self.requests = [t for t in self.requests if now - t < self.window]
        return max(0, self.limit - len(self.requests))

    @property
    def reset_at(self) -> float:
        if self.requests:
            return self.requests[0] + self.window
        return time.time() + self.window


class RateLimiter:
    """限流器。"""

    def __init__(self):
        self._limits: dict[str, RateLimitEntry] = {}
        # key: "ip:path" 或 "user_id:path"

    def get_key(self, request: Request, user_id: Optional[int] = None) -> str:
        """生成限流键。"""
        if user_id:
            return f"user:{user_id}:{request.url.path}"
        ip = self._get_client_ip(request)
        return f"ip:{ip}:{request.url.path}"

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端 IP。"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def is_allowed(
        self,
        request: Request,
        limit: int,
        window: int,
        user_id: Optional[int] = None,
    ) -> bool:
        """检查限流。"""
        key = self.get_key(request, user_id)
        if key not in self._limits:
            self._limits[key] = RateLimitEntry(limit, window)
        return self._limits[key].is_allowed()

    def get_headers(self, request: Request, user_id: Optional[int] = None) -> dict:
        """获取限流响应头。"""
        key = self.get_key(request, user_id)
        entry = self._limits.get(key)
        if not entry:
            return {}
        return {
            "X-RateLimit-Limit": str(entry.limit),
            "X-RateLimit-Remaining": str(entry.remaining),
            "X-RateLimit-Reset": str(int(entry.reset_at)),
        }


# 全局限流器实例
rate_limiter = RateLimiter()

# 端点限流配置
RATE_LIMIT_RULES = {
    # 认证端点
    "/api/auth/login": (5, 60),      # 5 次/分钟
    "/api/auth/register": (5, 60),   # 5 次/分钟
    # 偷菜
    "/api/steal/": (10, 60),         # 10 次/分钟
    # 种植/收获
    "/api/crops/plant": (30, 60),
    "/api/crops/harvest": (30, 60),
    # 管理端点
    "/api/admin/": (30, 60),         # 管理员 30 次/分钟
}

DEFAULT_GET_LIMIT = 60      # 60 次/分钟
DEFAULT_WRITE_LIMIT = 20    # 20 次/分钟


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件。"""

    async def dispatch(self, request: Request, call_next):
        # 跳过静态文件和文档端点
        if (
            request.url.path.startswith("/static/")
            or request.url.path in ("/docs", "/openapi.json", "/redoc")
        ):
            return await call_next(request)

        # 获取用户 ID（如果已认证）
        user_id = None
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # 简化：从 token 解析 user_id
            user_id = self._parse_user_id(token)

        # 查找匹配的规则
        path = request.url.path
        limit = DEFAULT_WRITE_LIMIT if request.method in ("POST", "PUT", "DELETE") else DEFAULT_GET_LIMIT
        window = 60

        for rule_path, (rule_limit, rule_window) in RATE_LIMIT_RULES.items():
            if path.startswith(rule_path):
                limit = rule_limit
                window = rule_window
                break

        # 检查限流
        allowed = rate_limiter.is_allowed(request, limit, window, user_id)
        headers = rate_limiter.get_headers(request, user_id)

        if not allowed:
            return Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers=headers,
            )

        # 执行请求
        response = await call_next(request)

        # 添加限流头
        for key, value in headers.items():
            response.headers[key] = value

        return response

    @staticmethod
    def _parse_user_id(token: str) -> Optional[int]:
        """从 token 中解析 user_id（简化）。"""
        # TODO: 实现真实的 token 验证
        return None
```

---

## 响应头

| 头部 | 说明 |
|---|---|
| `X-RateLimit-Limit` | 限流上限 |
| `X-RateLimit-Remaining` | 剩余请求数 |
| `X-RateLimit-Reset` | 重置时间戳 |

---

## 在 `main.py` 中注册

```python
# app/main.py
from app.middleware.rate_limit import RateLimitMiddleware

app.add_middleware(RateLimitMiddleware)
```

---

*文档生成时间: 2025-07-10*
