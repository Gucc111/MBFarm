# Core — 基础设施层

## 职责

`core/` 是整个项目的底层基础设施，提供所有其他模块依赖的基础能力：

```
core/
├── config.py         ← 配置管理（环境变量、应用设置）
├── database.py       ← 数据库连接（引擎、会话、Base）
├── security.py       ← 安全工具（密码哈希、Session 管理）
├── exceptions.py     ← 异常定义（业务异常、HTTP 映射）
├── dependencies.py   ← DI 工厂（FastAPI Depends 提供者）
└── constants.py      ← 游戏常量（作物、体力、等级、地块）
```

## 协作关系

```
routes/ ──Depends──→ dependencies.py ──实例化──→ services/
                                         │
                                    database.py (get_db)
                                         │
                                    config.py (settings)
                                         │
                                    security.py (哈希/会话)
                                         │
                                    exceptions.py (异常映射)
                                         │
                                    constants.py (作物/体力/等级)
```

- **config** 是最底层，被所有模块引用
- **database** 依赖 config（读取 DATABASE_URL）
- **security** 依赖 config（读取 SECRET_KEY）
- **dependencies** 聚合以上模块，向外暴露 DI 工厂
- **exceptions** 独立存在，被全局异常处理器和 routes 使用
- **constants** 独立存在，被 services/ 和 routes/ 读取

## 设计原则

1. **无业务逻辑**：core 只提供服务能力，不碰任何游戏规则
2. **纯工具性质**：所有输出都是其他模块可直接使用的对象/函数
3. **配置外置**：通过环境变量和 `.env` 文件管理，不写死

## 各模块概览

| 模块 | 输入 | 输出 | 被谁使用 |
|------|------|------|----------|
| config | `.env` 环境变量 | `Settings` 实例 | 全模块 |
| database | `Settings.database_url` | `AsyncSession`, `Base` | repositories, dependencies |
| security | `Settings.secret_key` | 哈希值, Session Cookie | auth_service, dependencies |
| exceptions | — | 异常类 | 全局处理器, routes |
| dependencies | db, settings, security | DI 函数 | routes (via Depends) |
| constants | — | 游戏常量数据类 | services/, routes/ |
