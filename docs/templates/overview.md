# 前端模板结构

## 目录结构

```
templates/
├── base.html                 # 基础模板（布局、导航、侧栏）
├── index.html                # 首页（农场主视图）
├── login.html                # 登录页
├── register.html             # 注册页
├── farm.html                 # 农场主页面（作物网格）
├── friend_farm.html          # 好友农场页面（偷菜用）
├── leaderboard.html          # 排行榜页面
├── achievements.html         # 成就页面
├── notifications.html        # 通知页面
└── admin/
    ├── index.html            # 管理后台首页
    ├── users.html            # 用户管理
    └── stats.html            # 数据统计

static/
├── css/
│   ├── main.css              # 全局样式
│   ├── farm.css              # 农场网格样式
│   ├── navigation.css        # 导航样式
│   └── admin.css             # 管理后台样式
├── js/
│   ├── main.js               # 全局 JS（API 调用、工具函数）
│   ├── farm.js               # 农场交互（种植、收获）
│   ├── steal.js              # 偷菜交互
│   ├── ws.js                 # WebSocket 连接管理
│   └── admin.js              # 管理后台 JS
└── images/
    ├── crops/                # 作物图片
    ├── icons/                # 图标
    └── backgrounds/          # 背景图
```

---

## 模板继承关系

```
base.html (基础布局)
├── index.html (首页重定向到 farm.html)
├── login.html
├── register.html
└── farm.html (主要游戏界面)
    ├── friend_farm.html
    ├── leaderboard.html
    ├── achievements.html
    └── notifications.html
└── admin/index.html (管理后台)
    ├── admin/users.html
    └── admin/stats.html
```

---

## `base.html` 关键结构

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}MB Farm{% endblock %}</title>
    <link rel="stylesheet" href="/static/css/main.css">
    <link rel="stylesheet" href="/static/css/navigation.css">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- 顶部导航 -->
    <nav class="navbar">
        <a href="/farm" class="nav-brand">🌾 MB Farm</a>
        <div class="nav-links">
            <a href="/farm">我的农场</a>
            <a href="/friend-farm">好友农场</a>
            <a href="/leaderboard">排行榜</a>
            <a href="/achievements">成就</a>
            <a href="/notifications">通知 <span class="badge">{{ unread_count }}</span></a>
            {% if current_user.is_admin %}
            <a href="/admin">管理后台</a>
            {% endif %}
        </div>
        <div class="nav-user">
            <span>{{ current_user.username }}</span>
            <a href="/logout">退出</a>
        </div>
    </nav>

    <!-- 主内容区 -->
    <main class="container">
        {% block content %}{% endblock %}
    </main>

    <!-- 通知弹窗 -->
    <div id="notification-panel" class="notification-panel" style="display: none;">
        <!-- WebSocket 推送通知显示 -->
    </div>

    <script src="/static/js/main.js"></script>
    <script src="/static/js/ws.js"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

---

## `farm.html` 关键结构

```html
{% extends "base.html" %}

{% block title %}我的农场 - MB Farm{% endblock %}

{% block content %}
<div class="farm-container">
    <!-- 农场信息 -->
    <div class="farm-header">
        <h2>{{ current_user.username }} 的农场</h2>
        <div class="farm-stats">
            <span>💰 {{ gold }}</span>
            <span>🌾 收获: {{ total_harvested }}</span>
        </div>
    </div>

    <!-- 作物网格 (25 格) -->
    <div class="plot-grid">
        {% for plot in plots %}
        <div class="plot" data-plot-index="{{ plot.index }}">
            {% if plot.crop %}
                <img src="/static/images/crops/{{ plot.crop.type }}_{{ plot.crop.growth_stage }}.png"
                     alt="{{ plot.crop.type }}">
                {% if plot.crop.is_mature %}
                <span class="mature-badge">成熟!</span>
                {% endif %}
            {% else %}
                <span class="empty-plot">空地</span>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <!-- 操作面板 -->
    <div class="action-panel">
        <button id="btn-plant" onclick="showPlantModal()">种植</button>
        <button id="btn-harvest" onclick="harvestSelected()">收获</button>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="/static/js/farm.js"></script>
{% endblock %}
```

---

## 前端 API 调用模式 (`main.js`)

```javascript
// API 基础 URL
const API_BASE = '/api';

// 获取认证 token（从 cookie 或 localStorage）
function getAuthHeader() {
    const token = localStorage.getItem('auth_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

// 通用 API 调用
async function apiFetch(url, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
        ...options.headers,
    };
    const response = await fetch(`${API_BASE}${url}`, {
        ...options,
        headers,
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || 'API 请求失败');
    }
    return response.json();
}

// 农场操作
async function plantCrop(plotIndex, seedType) {
    return apiFetch('/crops/plant', {
        method: 'POST',
        body: JSON.stringify({ plot_index: plotIndex, seed_type: seedType }),
    });
}

async function harvestCrop(plotIndex) {
    return apiFetch(`/crops/harvest/${plotIndex}`, { method: 'POST' });
}

async function stealCrop(targetUserId, plotIndex) {
    return apiFetch(`/steal/${targetUserId}?plot_index=${plotIndex}`, {
        method: 'POST',
    });
}

// 获取未读数
async function getUnreadCount() {
    try {
        const data = await apiFetch('/notifications/unread-count');
        return data.unread_count || 0;
    } catch {
        return 0;
    }
}
```

---

## WebSocket 连接 (`ws.js`)

```javascript
let ws = null;
let reconnectTimer = null;

function connectWebSocket(userId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = localStorage.getItem('auth_token');
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/${userId}?token=${token}`);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleNotification(data);
    };

    ws.onclose = () => {
        // 5 秒后重连
        reconnectTimer = setTimeout(() => connectWebSocket(userId), 5000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

function handleNotification(data) {
    // 显示通知弹窗
    const panel = document.getElementById('notification-panel');
    panel.innerHTML = `
        <h4>${data.title}</h4>
        <p>${data.message}</p>
    `;
    panel.style.display = 'block';
    setTimeout(() => { panel.style.display = 'none'; }, 5000);

    // 更新未读数
    updateUnreadBadge();
}
```

---

*文档生成时间: 2025-07-10*
