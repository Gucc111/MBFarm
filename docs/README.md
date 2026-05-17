# MB Farm — 项目文档

## 项目概述

MB Farm 是一个简易版 QQ 农场网页游戏，基于 Python + FastAPI + SQLite + Jinja2 构建，面向本地局域网的小型多人游戏。

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端 | Python + FastAPI | 轻量 REST API + WebSocket |
| 数据库 | SQLite + SQLAlchemy 2.0 (async) | 零配置，单文件存储 |
| 前端 | 纯 HTML + Jinja2 + 原生 CSS/JS | 无构建步骤 |
| 安全 | bcrypt + Server-side Session | Cookie 驱动的身份管理 |
| DI | FastAPI `Depends()` + 构造函数注入 | 零额外依赖 |
| 配置 | pydantic-settings | 类型安全、支持 `.env` |

---

## 应用架构

### 分层结构

```
┌─────────────────────────────────────────────────────────┐
│                   HTTP / WebSocket                       │
├───────────┬───────────────┬───────────────┬─────────────┤
│  routes/  │  (薄层: 请求   │  websocket/   │  middleware/│
│           │   校验、响应   │               │             │
├───────────┼───────────────┼───────────────┼─────────────┤
│ services/ │  (厚层: 业务  │  workers/     │             │
│           │   逻辑、规则   │  (定时任务)    │             │
├───────────┼───────────────┼───────────────┼─────────────┤
│ repositories/ │  (数据访问:  │ models/      │ config/     │
│              │   纯 CRUD)    │ (ORM 模型)   │ (常量/配置)  │
├───────────┴───────────────┴───────────────┴─────────────┤
│                       core/                              │
│  config │ database │ security │ exceptions │ dependencies│
│  (基础设施层，全模块共享)                                  │
├─────────────────────────────────────────────────────────┤
│                  SQLite (aiosqlite)                      │
└─────────────────────────────────────────────────────────┘
```

### 调用链

```
路由层 (routes/)          服务层 (services/)        仓库层 (repositories/)
      │                        │                          │
  POST /auth/login     ──→  AuthService.login()   ──→  UserRepository
      │                        │                        ──→  SessionRepository
      │                        │
  → 返回 200 + Cookie    → 事务提交/回滚           → 执行 SQL
```

### 设计原则

1. **薄路由，厚服务** — routes 只做校验和响应编排，业务逻辑在 services
2. **显式依赖** — 通过构造函数注入，不用全局变量或单例
3. **单一职责** — 每个 repository 只操作一个聚合根
4. **异步优先** — 全链路 `async/await`，充分利用并发
5. **渐进式开发** — 按 P0 → P1 → P2 → P3 迭代

---

## 开发优先级

| 优先级 | 名称 | 范围 | 说明 |
|--------|------|------|------|
| **P0** | 基础设施 & 认证 | core, models/user, schemas, repositories, services/auth, routes/auth, main | 可运行、可注册登录 |
| **P1** | 核心玩法 | models/farm, item, inventory, social, trade; 各对应 repo/service/route | 种植→收获→买卖闭环 |
| **P2** | 社交 & 润色 | 好友、偷菜、成就、WebSocket 通知、排行榜 | 社交互动与体验 |
| **P3** | 锦上添花 | 宠物系统、天气、离线收益、移动端适配 | 可选功能 |

详见 `docs/main.md` 获取 P0 阶段的完整开发清单。

---

## 目录结构

```
MBFarm/
├── app/                         # 应用源代码
│   ├── main.py                  # FastAPI 入口
│   ├── core/                    # 基础设施层
│   ├── models/                  # ORM 模型
│   ├── schemas/                 # Pydantic 校验模型
│   ├── repositories/            # 数据访问层
│   ├── services/                # 业务逻辑层
│   ├── routes/                  # HTTP 路由
│   ├── workers/                 # 后台定时任务
│   ├── middleware/              # HTTP 中间件
│   ├── templates/               # Jinja2 模板
│   └── static/                  # 静态资源 (CSS/JS/图片)
├── docs/                        # 项目文档 (当前目录)
├── tests/                       # 测试
├── scripts/                     # 辅助脚本 (初始化数据、重置 DB 等)
├── alembic/                     # 数据库迁移
├── .env.example                 # 环境变量模板
├── .env                         # 本地配置 (不提交)
├── requirements.txt
└── README.md
```

---

## 文档结构

```
docs/
├── README.md              ← 你正在看的文件
├── main.md                ← FastAPI 应用入口 & P0 开发清单
│
├── core/                  ← 基础设施层 (7 文档)
│   ├── README.md          ← 基础设施层概览
│   ├── config.md          ← 配置管理 (pydantic-settings)
│   ├── database.md        ← 数据库连接 (SQLAlchemy 2.0 async)
│   ├── security.md        ← 安全工具 (bcrypt + DB Session)
│   ├── exceptions.md      ← 异常体系 (AppError + 全局处理器)
│   ├── dependencies.md    ← DI 工厂 (FastAPI Depends + 构造函数注入)
│   └── constants.md       ← 游戏常量 (作物/体力/等级/地块配置)
│
├── models/                ← ORM 数据模型 (7 文档)
│   ├── user.md            ← User 与 Session 模型
│   ├── farm.md            ← Plot 地块 + Crop 作物模型
│   ├── item.md            ← Inventory 背包物品模型
│   ├── social.md          ← Friendship 好友关系模型
│   ├── achievement.md     ← 成就系统模型
│   └── notification.md    ← 通知模型
│
├── schemas/               ← Pydantic 校验模型 (9 文档)
│   ├── user.md            ← 用户注册/登录/响应
│   ├── farm.md            ← 种植/收获/浇水/农场响应
│   ├── item.md            ← 购买/出售/背包/商店
│   ├── shop.md            ← 商店商品列表/交易
│   ├── social.md          ← 好友添加/审批/列表
│   ├── notification.md    ← 通知列表/已读/WS 载荷
│   ├── steal.md           ← 偷菜请求/结果/历史
│   ├── achievement.md     ← 成就进度/解锁事件
│   └── leaderboard.md     ← 排行榜条目/分页
│
├── repositories/          ← 数据访问层 (4 文档)
│   ├── user.md            ← 用户 + Session 数据访问
│   ├── farm.md            ← 地块 + 作物数据访问
│   ├── item.md            ← 背包数据访问
│   └── social.md          ← 好友数据访问
│
├── services/              ← 业务逻辑层 (9 文档)
│   ├── auth.md            ← 注册/登录/登出
│   ├── game_engine.md     ← 核心规则引擎 (纯函数)
│   ├── farm.md            ← 种植/收获/浇水/体力
│   ├── shop.md            ← 商店买卖
│   ├── friend.md          ← 好友管理
│   ├── steal.md           ← 偷菜系统
│   ├── achievement.md     ← 成就检查/奖励发放
│   ├── notification.md    ← 通知持久化 + 实时推送
│   └── leaderboard.md     ← 排行榜计算
│
├── routes/                ← HTTP 路由层 (9 文档)
│   ├── auth.md            ← 注册/登录/登出/当前用户
│   ├── farm.md            ← 农场操作端点
│   ├── shop.md            ← 商店操作端点
│   ├── social.md          ← 社交操作端点
│   ├── steal.md           ← 偷菜端点
│   ├── achievement.md     ← 成就查询端点
│   ├── leaderboard.md     ← 排行榜端点
│   ├── notification.md    ← 通知 REST + WebSocket 端点
│   └── admin.md           ← 管理后台端点
│
├── middleware/            ← 中间件 (1 文档)
│   └── rate_limit.md      ← 请求限流中间件
│
├── workers/               ← 后台任务 (1 文档)
│   └── scheduler.md       ← 定时任务 (Session清理/作物成熟通知)
│
└── templates/             ← 前端模板 (1 文档)
    └── overview.md        ← 模板体系概览 (继承/变量/过滤器)
```

### 文档编写规范

- 每个模块文档结构统一：模块职责 → 设计决策 → 实现方案 → 使用方式
- 文档中的代码可直接复制到对应源文件中使用
- 后续每个阶段在 `docs/` 下新建对应目录

---

## 关键数据模型 (P0 阶段)

### User

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer (PK) | 自增主键 |
| `username` | String(32) | 唯一，不可为空 |
| `password_hash` | String(128) | bcrypt 哈希值 |
| `coins` | Integer | 初始 500 |
| `xp` | Integer | 初始 0 |
| `level` | Integer | 初始 1 |
| `created_at` | DateTime | 创建时间 |

### Session

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer (PK) | 自增主键 |
| `user_id` | Integer (FK) | 关联 User |
| `token` | String(64) | UUID4，唯一，存于 Cookie |
| `expires_at` | DateTime | 过期时间 |
| `created_at` | DateTime | 创建时间 |

---

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 创建 .env 文件
cp .env.example .env
# 编辑 .env 填入 SECRET_KEY

# 启动开发服务器
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 局域网访问
# 本机: http://localhost:8000
# 其他设备: http://<本机IP>:8000
```
