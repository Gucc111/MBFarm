# 配置模块 (Config)

> 管理 MB Farm 应用的所有运行时配置，实现配置与代码解耦，支持环境隔离。

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **集中管理配置** | 所有配置项统一在一个位置定义，避免硬编码 |
| **类型安全校验** | 利用 Pydantic 类型提示，在应用启动时自动校验配置格式 |
| **环境变量注入** | 支持通过 `.env` 文件和系统环境变量覆盖默认值 |
| **单例访问** | 提供全局唯一的 `settings` 实例，任何模块均可安全引入 |

---

## 2. 设计决策

### 为什么选择 `pydantic-settings`？

| 对比项 | `pydantic-settings` | `python-dotenv` | `configparser` |
|--------|---------------------|-----------------|-----------------|
| 类型校验 | ✅ 自动 | ❌ 需手动 | ❌ 无 |
| 默认值 | ✅ 支持 | ❌ 需手动 | ✅ 支持 |
| 与 Pydantic 生态 | ✅ 原生集成 | ❌ 独立 | ❌ 独立 |
| 启动时快速失败 | ✅ 配置错误立即报错 | ❌ 运行时才暴露 | ❌ 运行时才暴露 |
| 简洁性 | ✅ 类定义即配置 | ✅ 简单 | ❌ 配置文件格式复杂 |

**结论**：MB Farm 已经使用了 Pydantic（作为 FastAPI 数据验证基础），`pydantic-settings` 可以无缝集成，零学习成本，且提供其他方案无法比拟的类型安全保障。

### 核心原则

1. **配置即代码** — 配置项通过 Pydantic BaseModel 定义，享受完整的类型检查和 IDE 补全。
2. **分层优先级** — 系统环境变量 > `.env` 文件 > 代码默认值。
3. **启动时校验** — 配置错误导致应用启动失败，避免运行时出现难以追踪的问题。
4. **只读实例** — `settings` 是单例实例，应用运行期间不可修改。

---

## 3. 配置项列表

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """MB Farm 应用配置"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,       # 环境变量名大小写不敏感
        extra="ignore",             # 忽略 .env 中未定义的键
    )
    
    # ===== 应用基础配置 =====
    APP_NAME: str = Field(default="MB Farm", description="应用名称")
    APP_VERSION: str = Field(default="0.1.0", description="应用版本")
    DEBUG: bool = Field(default=False, description="调试模式开关")
    
    # ===== 安全配置 =====
    SECRET_KEY: str = Field(
        default="change-me-in-production",
        description="用于签名 Session 和 JWT 的密钥，生产环境必须修改"
    )
    
    # ===== 数据库配置 =====
    DATABASE_URL: str = Field(
        default="sqlite:///./mbfarm.db",
        description="数据库连接字符串，默认使用 SQLite 本地文件"
    )
    
    # ===== JWT 配置 =====
    JWT_EXPIRE_MINUTES: int = Field(
        default=1440,
        ge=1,
        description="JWT Token 有效期（分钟），默认 24 小时"
    )
    
    # ===== 服务器配置 =====
    HOST: str = Field(default="0.0.0.0", description="监听地址")
    PORT: int = Field(default=8000, ge=1, le=65535, description="监听端口")


# ===== 单例实例 =====
settings = Settings()
```

### 配置项详解

| 配置项 | 类型 | 默认值 | 环境变量名 | 说明 |
|--------|------|--------|-----------|------|
| `APP_NAME` | `str` | `"MB Farm"` | `APP_NAME` | 应用显示名称 |
| `APP_VERSION` | `str` | `"0.1.0"` | `APP_VERSION` | 语义化版本号 |
| `DEBUG` | `bool` | `False` | `DEBUG` | 调试模式，开启后返回详细错误信息 |
| `SECRET_KEY` | `str` | `"change-me-in-production"` | `SECRET_KEY` | **敏感信息**，生产环境必须替换为强随机字符串 |
| `DATABASE_URL` | `str` | `"sqlite:///./mbfarm.db"` | `DATABASE_URL` | SQLAlchemy 兼容的连接字符串 |
| `JWT_EXPIRE_MINUTES` | `int` | `1440` | `JWT_EXPIRE_MINUTES` | JWT Token 有效期，最小值为 1 |
| `HOST` | `str` | `"0.0.0.0"` | `HOST` | 服务监听地址，`0.0.0.0` 允许局域网访问 |
| `PORT` | `int` | `8000` | `PORT` | 服务监听端口，范围 1-65535 |

### 约束规则

- `JWT_EXPIRE_MINUTES`: 最小值 1（通过 `ge=1` 约束）
- `PORT`: 合法端口范围 1-65535（通过 `ge=1, le=65535` 约束）
- 所有布尔配置支持 Python 的 `True`/`False` 以及字符串 `true`/`false`

---

## 4. 实现方案

### 文件位置

```
mbfarm/
├── app/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          ← 配置模块
│   │   ├── database.py
│   │   └── exceptions.py
│   └── main.py
├── .env                       ← 环境变量文件（见下文示例）
├── .env.example              ← 配置模板
└── ...
```

### 核心接口

```python
# 1. 获取配置单例（任何模块直接使用）
from app.core.config import settings

print(settings.APP_NAME)        # "MB Farm"
print(settings.DATABASE_URL)    # "sqlite:///./mbfarm.db"
print(settings.JWT_EXPIRE_MINUTES)  # 1440

# 2. 运行时读取（不可修改）
settings.SECRET_KEY = "new-key"  # ❌ 报错：SettingsValuesFrozenError

# 3. 检查调试模式
if settings.DEBUG:
    print("调试模式已开启")
```

### 错误处理

```python
# 场景：SECRET_KEY 被设置为非字符串类型
# 结果：Pydantic 在初始化时抛出 ValidationError
try:
    settings = Settings()
except Exception as e:
    print(f"配置加载失败: {e}")
    # 应用应在启动时捕获此异常并退出
```

---

## 5. .env 文件示例

### `.env.example`（提交到版本库，不包含真实密钥）

```bash
# MB Farm 应用配置
APP_NAME=MB Farm
APP_VERSION=0.1.0

# 开发环境开启调试模式
DEBUG=true

# 生产环境必须修改此密钥！
# 生成方式: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=change-me-in-production

# SQLite 数据库路径
DATABASE_URL=sqlite:///./mbfarm.db

# JWT Token 有效期（分钟）
JWT_EXPIRE_MINUTES=1440

# 服务器监听配置
HOST=0.0.0.0
PORT=8000
```

### `.env`（本地开发，已加入 `.gitignore`）

```bash
# MB Farm 应用配置
DEBUG=true
SECRET_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
DATABASE_URL=sqlite:///./mbfarm.db
JWT_EXPIRE_MINUTES=1440
HOST=0.0.0.0
PORT=8000
```

### `.gitignore` 规则

```
# 环境变量（包含敏感配置）
.env
```

---

## 6. 使用方式

### 在其他模块中引入配置

```python
# 示例 1: 在数据库模块中使用
from app.core.config import settings
from sqlalchemy import create_engine

engine = create_engine(settings.DATABASE_URL)
```

```python
# 示例 2: 在 JWT 认证模块中使用
from app.core.config import settings
from jose import jwt

token = jwt.encode(
    {"sub": user_id},
    settings.SECRET_KEY,
    algorithm="HS256"
)
# 过期时间从配置读取
expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
```

```python
# 示例 3: 在 FastAPI 应用启动配置中使用
from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)
```

```python
# 示例 4: 在服务层中使用
from app.core.config import settings

class UserService:
    def get_config(self):
        """返回当前应用的运行配置（不含敏感信息）"""
        return {
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "debug": settings.DEBUG,
            "jwt_expire_minutes": settings.JWT_EXPIRE_MINUTES,
        }
```

### 生产环境部署

```bash
# 方式 1: 通过系统环境变量注入
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export DATABASE_URL=sqlite:///./data/mbfarm.db
export DEBUG=false
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 方式 2: 通过 docker-compose 环境变量
# docker-compose.yml:
# environment:
#   - SECRET_KEY=${SECRET_KEY}
#   - DATABASE_URL=sqlite:///./data/mbfarm.db
#   - DEBUG=false
```

---

## 7. 扩展说明

### 添加新配置项

```python
# 在 Settings 类中添加新字段
class Settings(BaseSettings):
    # ... 现有配置 ...
    
    SMTP_HOST: str = Field(default="localhost", description="SMTP 服务器地址")
    SMTP_PORT: int = Field(default=587, ge=1, description="SMTP 端口")
    
    # Pydantic 会自动校验类型和约束，无需额外代码
```

### 条件配置（高级用法）

如果未来需要区分开发/测试/生产环境，可以使用嵌套的环境文件：

```python
model_config = SettingsConfigDict(
    env_file=f".env.{os.getenv('ENVIRONMENT', 'development')}",
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore",
)
```

对应文件：
- `.env.development` — 开发环境
- `.env.production` — 生产环境

---

## 8. 依赖

```txt
# requirements.txt 中已包含
pydantic-settings>=2.0.0
```

**无额外依赖** — `pydantic-settings` 是 `pydantic` 官方维护的插件，与项目已有依赖完全兼容。
