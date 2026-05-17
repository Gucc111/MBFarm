# MB Farm — 体验指南

> 基于 Python/FastAPI/SQLite/Jinja2 的简易 QQ 农场网页游戏，面向本地局域网小型社群（约十几人）。

---

## 1. 快速部署

### 1.1 安装依赖

```bash
pip install -r requirements.txt
```

### 1.2 配置

项目根目录下创建 `.env` 文件（可复制 `.env.example`）：

```bash
cp .env.example .env
```

`.env` 文件配置说明：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `HOST` | `0.0.0.0` | 监听地址（局域网设为 `0.0.0.0` 即可被访问） |
| `PORT` | `8000` | 服务端口 |
| `SECRET_KEY` | `change-me-in-production` | Session 签名密钥，生产环境请修改 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./mbfarm.db` | SQLite 数据库路径 |
| `DEBUG` | `true` | 调试模式开关，生产环境建议 `false` |
| `JWT_EXPIRE_MINUTES` | `1440` | Session 有效期（分钟），默认 24 小时 |

> **注意**: 局域网部署时将 `HOST` 保持 `0.0.0.0`，其他人通过 `http://你的IP:端口` 访问。

### 1.3 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

开发环境可加 `--reload` 参数实现热重载：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动后访问 `http://localhost:8000` 即可看到登录页面。

### 1.4 浏览器访问

| 地址 | 说明 |
|---|---|
| `http://localhost:8000` | 首页（自动跳转到农场页面） |
| `http://localhost:8000/login` | 登录页 |
| `http://localhost:8000/register` | 注册页 |
| `http://localhost:8000/farm` | 我的农场（需登录） |
| `http://localhost:8000/friend-farm` | 好友农场 / 偷菜（需登录） |
| `http://localhost:8000/docs` | Swagger API 文档（需登录） |

### 1.5 后台运行

如需后台持续运行（推荐部署方式）：

```bash
# 方式 1: 使用 nohup
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > mbfarm.log 2>&1 &

# 方式 2: 使用 screen / tmux
screen -S mbfarm
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Ctrl+A, D 分离会话

# 停止服务
pkill -f "uvicorn app.main"
```

---

## 2. 游戏概述

### 2.1 核心玩法

MB Farm 复刻经典 QQ 农场的核心体验：

```
买种子 → 种在地块 → 浇水加速 → 等成熟 → 收获赚钱 → 升级解锁
                ↑                              ↓
                └──── 偷好友的成熟作物 ← 加好友 ──┘
```

### 2.2 资源系统

| 资源 | 初始值 | 说明 |
|---|---|---|
| 💰 金币 | 500 | 买种子、解锁地块 |
| ⚡ 体力 | 100 | 种植/浇水/收获/偷菜消耗 |
| 📊 等级 | 1 | 最高 10 级，解锁高级作物 |
| ⭐ 经验 | 0 | 收获作物获得 |

### 2.3 体力规则

- 上限 100 点
- 在线时每次操作后自动恢复离线期间体力
- 离线期间每分钟恢复 1 点体力
- 不同操作消耗：种植 5、收获 3、浇水 2、偷菜 3

---

## 3. 作物图鉴

| 作物 | 购买价 | 收获价 | 基础生长时间 | 需等级 | 每次浇水加速 |
|---|---|---|---|---|---|
| 🌾 小麦 | 10 | 18 | 30 分钟 | 1 | 5 分钟 |
| 🥕 胡萝卜 | 30 | 55 | 2 小时 | 2 | 15 分钟 |
| 🍅 番茄 | 80 | 150 | 6 小时 | 3 | 30 分钟 |
| 🍓 草莓 | 200 | 400 | 12 小时 | 5 | 1 小时 |
| 🌻 向日葵 | 500 | 1000 | 24 小时 | 8 | 1.5 小时 |

> 💡 浇水可以缩短作物生长时间，最快减至 30%，即最多减少 70% 生长时间。

---

## 4. 农场系统

### 4.1 地块

- 初始解锁 **9 块**耕地
- 最大可解锁 **25 块**
- 每块新地块消耗 **200 金币**

### 4.2 种植流程

1. 去商店购买种子（见第 5 节）
2. 点击农场空地块，选择种子种植
3. 浇水加速生长
4. 成熟后点击收获，获得金币和 XP

### 4.3 操作要求

| 操作 | 条件 | 消耗 |
|---|---|---|
| 种植 | 地块为空 + 有对应种子 + 等级达标 + 体力足够 | 1 颗种子 + 5 体力 |
| 浇水 | 地块有未成熟作物 + 体力足够 | 2 体力 |
| 收获 | 作物成熟 + 体力足够 | 3 体力 |

---

## 5. 商店系统

### 5.1 在网页中购买

在农场页面点击底部「🏪 商店」标签，即可查看和购买种子。

### 5.2 API 方式（高级用法）

查看商店：

```bash
GET /api/shop/seeds
```

购买种子：

```bash
POST /api/shop/buy
Content-Type: application/json

{
    "seed_type": "wheat",
    "quantity": 10
}
```

- `seed_type` 见作物图鉴
- 购买直接消耗金币，种子进入背包

---

## 6. 社交系统

### 6.1 添加好友

在网页「好友农场」页面，输入好友用户名即可发送好友请求。

**API 方式：**

```bash
POST /api/social/friend/request
Content-Type: application/json

{
    "friend_username": "someplayer"
}
```

好友上限 **50 人**。发送后对方会在待处理请求中看到。

### 6.2 审批好友请求

在网页中直接点击「✓」接受或「✗」拒绝。

**API 方式：**

```bash
POST /api/social/friend/respond
Content-Type: application/json

{
    "friendship_id": 1,
    "accept": true          // true=接受, false=拒绝
}
```

### 6.3 查看好友列表

```bash
GET /api/social/friends
```

### 6.4 查看待处理请求

```bash
GET /api/social/requests/pending
```

### 6.5 解除好友

```bash
POST /api/social/friend/remove
Content-Type: application/json

{
    "target_user_id": 2
}
```

### 6.6 拉黑用户

```bash
POST /api/social/friend/block
Content-Type: application/json

{
    "target_user_id": 2
}
```

---

## 7. 偷菜系统

### 7.1 偷取好友作物

在网页「好友农场」页面点击好友，即可查看其农场并偷取成熟作物。

**API 方式：**

```bash
POST /api/steal/{target_user_id}
```

- 只能偷好友的 **已成熟** 作物
- 随机选择一个成熟地块
- 偷到的作物进入你的背包
- 消耗 **3 体力**

### 7.2 限制

| 限制 | 说明 |
|---|---|
| 冷却时间 | 对同一目标 **30 分钟** 内只能偷一次 |
| 每日上限 | 每天最多偷 **3 次** |
| 好友关系 | 必须是好友才能偷 |
| 自偷禁止 | 不能偷自己的作物 |

### 7.3 查看记录

```bash
GET /api/steal/my        # 我偷了谁
GET /api/steal/me        # 谁偷了我
```

---

## 8. 认证（登录）

> 所有农场、商店、社交、偷菜操作都需要先登录（Session Cookie 机制）。

### 8.1 注册

在浏览器访问注册页面，填写用户名和密码即可。

**API 方式：**

```bash
POST /api/auth/register
Content-Type: application/json

{
    "username": "myname",
    "password": "mypass123"
}
```

新用户初始：金币 500、体力 100、等级 1、经验 0、9 块地块。

### 8.2 登录

在浏览器登录页面输入用户名和密码。

**API 方式：**

```bash
POST /api/auth/login
Content-Type: application/json

{
    "username": "myname",
    "password": "mypass123"
}
```

登录成功后浏览器自动存储 `session_token` Cookie，后续请求自动携带。

### 8.3 登出

```bash
POST /api/auth/logout
```

或在网页右上角点击「退出」按钮。

### 8.4 查看当前用户

```bash
GET /api/auth/me
```

---

## 9. 农场完整信息（一站式查看）

```bash
GET /api/farm/info
```

返回完整的农场快照：

```json
{
    "user": {
        "id": 1,
        "username": "myname",
        "coins": 500,
        "stamina": 100,
        "xp": 0,
        "level": 1
    },
    "plots": [
        {
            "index": 1,
            "level": 1,
            "crop": {
                "seed_type": "wheat",
                "seed_name": "小麦",
                "plant_time": "2026-05-17T10:00:00Z",
                "watered_times": 2,
                "is_mature": false,
                "growth_stage": "growing",
                "mature_at": "2026-05-17T10:35:00Z"
            },
            "watered_times": 2,
            "planted_at": "2026-05-17T10:00:00Z"
        }
    ],
    "max_plots": 25
}
```

### 生长阶段

| 阶段 | 进度 | 说明 |
|---|---|---|
| `seedling` | 0% ~ 25% | 萌芽期 |
| `growing` | 25% ~ 75% | 生长期 |
| `almost_mature` | 75% ~ 100% | 即将成熟 |
| `mature` | 100% | 可以收获！ |

---

## 10. 完整游玩流程示例

以 **两个玩家**（A 和 B）为例：

### 网页方式（推荐）

```
第一步：打开浏览器，分别注册账号
  A → 访问 /register 注册
  B → 访问 /register 注册

第二步：加好友
  A → 进入「好友农场」页面 → 输入 B 的用户名 → 发送请求
  B → 在好友农场页面 → 点击「✓」接受请求

第三步：A 买种子并种植
  A → 进入「我的农场」→ 点击「🏪 商店」→ 购买小麦种子
  A → 点击空地块 → 选择小麦 → 种植
  A → 点击 💧 浇水按钮 → 加速生长

第四步：A 等作物成熟（最短约 10.5 分钟，最多浇水 7 次）
  页面会自动刷新显示生长进度

第五步：B 来偷菜
  B → 进入「好友农场」→ 点击 A → 点击偷菜按钮

第六步：A 收获自己种的小麦
  A → 点击成熟地块 → 「收获」按钮 → 获得金币 + XP

第七步：A 升级解锁胡萝卜
  A → 查看等级变化 → 自动解锁新作物
```

### API 方式（高级用法）

```
第一步：各自注册并登录
  A → POST /api/auth/register
  B → POST /api/auth/register

第二步：加好友
  A → POST /api/social/friend/request  (添加 "b")
  B → POST /api/social/friend/respond  (接受请求)

第三步：A 买种子并种植
  A → GET  /api/shop/seeds             (查看价格)
  A → POST /api/shop/buy               (买小麦)
  A → POST /api/farm/plant             (种在地块 1)
  A → POST /api/farm/water             (浇水加速)

第四步：A 等作物成熟（最短约 10.5 分钟，最多浇水 7 次）
  A → GET  /api/farm/info              (查看生长进度)

第五步：B 来偷菜
  B → POST /api/steal/{A的user_id}     (偷到小麦，进入 B 的背包)

第六步：A 收获自己种的小麦
  A → POST /api/farm/harvest           (获得金币 + XP)

第七步：A 升级解锁胡萝卜
  A → GET  /api/farm/info              (查看当前等级)
```

---

## 11. 等级与经验

| 等级 | 累计 XP | 解锁作物 |
|---|---|---|
| 1 | 0 | 小麦 |
| 2 | 100 | 胡萝卜 |
| 3 | 300 | 番茄 |
| 5 | 1000 | 草莓 |
| 8 | 2800 | 向日葵 |
| 10 | 4500 | 满级 |

---

## 12. 前端架构

项目采用 **Jinja2 服务端渲染 + 原生 JavaScript** 的轻量级前端方案：

```
templates/          # Jinja2 HTML 模板
├── base.html       # 基础布局（导航栏、页脚、公共资源）
├── login.html      # 登录页
├── register.html   # 注册页
├── farm.html       # 我的农场（地块网格、商店、库存）
└── friend_farm.html # 好友农场（好友列表、偷菜）

static/             # 静态资源
├── css/
│   ├── main.css          # 全局样式 + 认证页 + Toast
│   ├── navigation.css    # 导航栏样式
│   └── farm.css          # 农场地块/商店/偷菜样式
└── js/
    ├── api.js            # API 客户端（所有后端接口封装）
    ├── crops.js          # 作物配置（Emoji、名称、生长时间）
    ├── farm.js           # 农场页面逻辑（种植/浇水/收获/自动刷新）
    ├── social.js         # 社交页面逻辑（好友/偷菜）
    ├── main.js           # 应用引导（Auth 检查、登录/注册表单）
    └── toast.js          # Toast 通知组件
```

**特点：**
- 无前端构建步骤，无需 Node.js/npm
- 浏览器直接渲染，无需编译
- 15 秒自动轮询农场状态，无需刷新页面
- 响应式设计，支持手机/平板/电脑

---

## 13. 技术备注

- **前端页面**: 浏览器访问 `http://你的IP:端口` 即可游玩
- **API 文档**: 访问 `http://你的IP:端口/docs` 查看 Swagger UI，可直接在线测试所有接口
- **数据库**: SQLite 单文件 (`mbfarm.db`)，备份只需复制文件
- **认证**: 基于 Cookie 的服务端 Session，过期时间 24 小时
- **跨设备**: 局域网内任意设备通过 `http://服务器IP:端口` 访问，共享同一个农场
