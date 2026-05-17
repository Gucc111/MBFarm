# `main.md` — FastAPI 应用入口

## 1. 模块职责

`app/main.py` 是 MB Farm 项目的**唯一入口文件**，负责：

- **创建** FastAPI 应用实例；
- **配置**全局中间件（CORS、Session、GZip）；
- **注册**所有功能路由（认证、游戏逻辑等）；
- **挂载**静态文件服务和 API 文档页面；
- **管理**应用生命周期（启动/关闭事件）。

**不处理**的业务：

- 路由逻辑（委托 `routes/`）；
- 业务规则（委托 `services/`）；
- 数据模型（委托 `models/` 和 `schemas/`）。

---

## 2. 应用配置

| 属性 | 值 | 说明 |
|------|------|------|
| `title` | `MB Farm` | 应用名称，显示在 Swagger UI 中 |
| `description` | `简易版 QQ 农场网页游戏` | 应用描述 |
| `version` | `0.1.0` | 语义化版本号 |
| `root_path` | 空字符串 `""` | 适配反向代理部署 |

---

## 3. 中间件链

中间件按以下顺序注册（请求时从上到下，响应时从下到上）：

### 3.1 CORS 中间件

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    allow_credentials=True,  # 允许携带 Cookie
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)
```

**安全注意**：生产环境应将 `allow_origins` 限制为实际的前端域名。

### 3.2 Session 中间件

```python
from fastapi.middleware.session import SessionMiddleware

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,  # 从环境变量读取
    max_age=3600 * 24 * 7,  # 7 天
    same_site="lax",  # CSRF 防护
    path="/",
)
```

### 3.3 GZip 中间件

```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,  # 响应体小于 1KB 不压缩
)
```

---

## 4. 静态文件与路由注册

### 4.1 静态文件

```python
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="static"), name="static")
```

挂载后，`static/` 目录下的文件可通过 `/static/xxx` 访问：

```
static/
├── css/
│   └── style.css       → /static/css/style.css
├── js/
│   └── game.js         → /static/js/game.js
└── images/
    └── farm.png        → /static/images/farm.png
```

### 4.2 路由注册

```python
from app.routes.auth import router as auth_router

app.include_router(auth_router)
```

未来扩展时继续追加：

```python
from app.routes.game import router as game_router
app.include_router(game_router, prefix="/api")
```

---

## 5. 生命周期事件

### 5.1 启动事件

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    await init_db()
    yield
    # 关闭时执行（可选清理）

app = FastAPI(lifespan=lifespan)
```

### 5.2 关闭事件

如需额外清理（如关闭 WebSocket 连接池）：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_websocket_pools()
```

---

## 6. 实现方案

完整实现代码：

```python
"""
app/main.py — MB Farm FastAPI 应用入口

所有中间件、路由、静态文件在此注册，作为应用唯一入口。
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.session import SessionMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.routes.auth import router as auth_router


# ------------------------------------------------------------------
# 生命周期管理
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    应用生命周期事件处理器。

    启动时：
    - 初始化数据库表（如果不存在）；

    关闭时：
    - 由 FastAPI 自动管理数据库连接池的清理。
    """
    # 启动：初始化数据库
    await init_db()

    yield

    # 关闭：如需额外清理，在此添加
    # await cleanup_resources()


# ------------------------------------------------------------------
# 应用实例
# ------------------------------------------------------------------

app = FastAPI(
    title="MB Farm",
    description="简易版 QQ 农场网页游戏",
    version="0.1.0",
    lifespan=lifespan,
    root_path="",  # 适配反向代理部署
)


# ------------------------------------------------------------------
# 中间件配置
# ------------------------------------------------------------------

# 1. CORS — 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境：允许所有来源
    # 生产环境建议替换为具体域名：
    # allow_origins=["http://localhost:3000", "http://yourdomain.com"],
    allow_credentials=True,  # 允许携带 Cookie（Session 必需）
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)

# 2. Session — 服务端 Session 存储
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,  # 从环境变量 MB_FARM_SECRET_KEY 读取
    max_age=3600 * 24 * 7,  # Session 最大存活 7 天
    same_site="lax",  # CSRF 防护
    path="/",  # 全站有效
)

# 3. GZip — 响应压缩
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,  # 响应体 >= 1KB 时压缩
)


# ------------------------------------------------------------------
# 静态文件挂载
# ------------------------------------------------------------------

# 挂载静态资源目录
# static/ 目录中的文件可通过 /static/<path> 访问
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ------------------------------------------------------------------
# 路由注册
# ------------------------------------------------------------------

# 注册认证路由
app.include_router(auth_router)

# 未来路由注册示例：
# from app.routes.game import router as game_router
# app.include_router(game_router)
# from app.routes.api import router as api_router
# app.include_router(api_router)


# ------------------------------------------------------------------
# 开发环境：API 文档
# ------------------------------------------------------------------

# 以下路由在开发环境中提供自动文档：
# - Swagger UI:  http://localhost:8000/docs
# - ReDoc:       http://localhost:8000/redoc
# - OpenAPI JSON: http://localhost:8000/openapi.json
#
# 生产环境建议关闭或添加访问控制：
# if settings.DEBUG:
#     ...
```

---

## 7. 启动方式

### 7.1 开发环境

```bash
# 方式 1：使用 uvicorn 直接启动
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 方式 2：使用 Python 模块启动
python -m uvicorn app.main:app --reload
```

`--reload` 参数启用热重载，修改代码后自动重启。

### 7.2 生产环境

```bash
# 使用多 worker 模式
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 7.3 环境变量

启动前设置必要的环境变量：

```bash
export MB_FARM_SECRET_KEY="your-secret-key-change-in-production"
export MB_FORM_DB_URL="sqlite+aiosqlite:///./mbfarm.db"
export MB_FARM_DEBUG="true"  # 生产环境设为 false
```

### 7.4 API 文档访问

启动后访问：

| 页面 | URL |
|------|-----|
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |
| OpenAPI JSON | `http://localhost:8000/openapi.json` |
| 健康检查（可选） | `http://localhost:8000/` |

---

## 8. 项目启动流程图

```
┌─────────────────────────────────────────────────────────────┐
│                     启动 uvicorn                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI 实例创建                                │
│  - 设置 title, description, version                        │
│  - 注册 lifespan 生命周期事件                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              lifespan 启动钩子                               │
│  - init_db() 初始化数据库表                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              中间件链注册                                     │
│  1. CORS 中间件                                             │
│  2. Session 中间件                                          │
│  3. GZip 中间件                                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              路由 & 静态文件注册                              │
│  - auth_router → /auth                                      │
│  - /static → static/ 目录                                   │
│  - /docs → Swagger UI                                       │
│  - /redoc → ReDoc                                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              服务器就绪                                       │
│  Listening on http://0.0.0.0:8000                          │
└─────────────────────────────────────────────────────────────┘
```
