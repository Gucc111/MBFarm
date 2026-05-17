# GameEngine — 游戏核心规则引擎

> **模块**: `app/services/game_engine.py`
>
> 封装所有游戏核心计算规则，包括作物成熟判定、生长阶段计算、经验值升级、体力恢复等。
> 所有函数均为**纯函数**（不修改数据库，无外部副作用），仅依赖输入参数计算返回值。

---

## 1. 模块职责

| 职责 | 说明 |
|------|------|
| **作物成熟判定** | `is_mature()`, `get_mature_at()` |
| **生长阶段计算** | `calc_growth_stage()` |
| **等级计算** | `calc_level_from_xp()` |
| **体力恢复计算** | `restore_stamina()` |

---

## 2. 设计决策

### 纯函数

本模块所有函数均为纯函数：

- **无副作用**：不读写数据库，不调用 Repository，不修改全局状态
- **输入确定 → 输出确定**：相同参数始终返回相同结果
- **易于测试**：可直接调用函数，无需 mock 数据库或依赖注入
- **线程安全**：无共享状态，支持并发调用

```python
from app.services.game_engine import is_mature, calc_growth_stage

is_mature(plant_time, grow_time, watered_times, water_bonus)
calc_growth_stage(plant_time, grow_time, watered_times, water_bonus)
```

### 时间系统约定

| 约定 | 说明 |
|------|------|
| **时区** | 所有时间使用 UTC（`datetime.now(timezone.utc)`） |
| **时间单位** | 作物生长时间以**秒**为单位，体力恢复以**分钟**为单位 |

### 作物生长算法

采用 **"浇水减时间"** 机制：

```
实际成熟所需时间 = grow_time - watered_times × water_bonus
最小实际时间 = max(实际成熟所需时间, grow_time × 0.3)   ← 30% 下限防秒熟
成熟时间 = plant_time + timedelta(seconds=最小实际时间)
```

---

## 3. 函数列表

| 函数 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `is_mature` | `(plant_time, grow_time, watered_times, water_bonus) → bool` | 作物是否已成熟 |
| `get_mature_at` | `(plant_time, grow_time, watered_times, water_bonus) → datetime` | 成熟时刻（UTC） |
| `calc_growth_stage` | `(plant_time, grow_time, watered_times, water_bonus) → str` | `"seedling"|"growing"|"almost_mature"|"mature"` |
| `calc_level_from_xp` | `(xp) → int` | 当前等级（1-based） |
| `restore_stamina` | `(current_stamina, last_active, max_stamina, restore_per_minute) → int` | 恢复后体力值 |

---

## 4. 函数详解

### `is_mature`

委托给 `get_mature_at()`，判断当前 UTC 时间是否已过成熟时刻。

### `get_mature_at`

计算作物成熟的具体 UTC 时间。实际成熟所需时间不低于 `grow_time * 0.3`。

```python
get_mature_at(
    plant_time=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
    grow_time=3600,
    watered_times=2,
    water_bonus=300,
)
# → 10:00 + 3000秒 → datetime(2025, 1, 1, 10, 50, 0)
```

### `calc_growth_stage`

按进度百分比返回阶段标签：

| 进度 | 阶段 |
|------|------|
| 0% – 25% | `seedling`（幼苗） |
| 25% – 75% | `growing`（生长中） |
| 75% – 100% | `almost_mature`（即将成熟） |
| ≥100% | `mature`（已成熟） |

### `calc_level_from_xp`

根据累计经验值从 `app.core.constants.LEVEL_XP_THRESHOLD` 表中查找等级（1-based）。

**注意**：此函数签名已简化为只接受 `xp` 参数，经验阈值表从 `app.core.constants` 自动导入，不再需要外部传入 `level_table`。

```python
LEVEL_XP_THRESHOLD = (0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500)

calc_level_from_xp(0)     → 1
calc_level_from_xp(99)    → 1
calc_level_from_xp(100)   → 2
calc_level_from_xp(300)   → 3
calc_level_from_xp(999)   → 4
calc_level_from_xp(4500)  → 10
```

### `restore_stamina`

```python
restore_stamina(
    current_stamina=20,
    last_active=datetime.now(timezone.utc) - timedelta(minutes=120),
    max_stamina=100,
    restore_per_minute=1,
)
# → min(20 + 120, 100) → 100
```

---

## 5. 测试策略

```python
# tests/test_game_engine.py
import unittest
from datetime import datetime, timezone, timedelta
from app.services.game_engine import (
    is_mature, get_mature_at, calc_growth_stage, calc_level_from_xp, restore_stamina,
)


def test_is_mature():
    past = datetime.now(timezone.utc) - timedelta(seconds=1000)
    assert is_mature(past, 1800, 0, 300) is False
    assert is_mature(past, 1800, 3, 300) is True  # 3*300=900, 1800-900=900, 1000>900


def test_get_mature_at():
    base = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
    mature = get_mature_at(base, 1800, 2, 300)
    assert mature == datetime(2026, 5, 17, 10, 20, 0, tzinfo=timezone.utc)


def test_calc_growth_stage():
    now = datetime.now(timezone.utc)
    assert calc_growth_stage(now, 1800, 0, 0) == "seedling"


def test_calc_level_from_xp():
    assert calc_level_from_xp(0) == 1
    assert calc_level_from_xp(100) == 2
    assert calc_level_from_xp(4500) == 10


def test_restore_stamina():
    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    assert restore_stamina(30, past, 100, 1) == 40
```

---

## 6. 使用方式

### FarmService 中调用

```python
from app.services.game_engine import is_mature, calc_growth_stage, get_mature_at

# 收获时判断成熟
if not is_mature(crop.plant_time, crop.duration, crop.watered_times, seed_config.water_bonus):
    raise AppValidationError("作物尚未成熟")

# 浇水后计算新的成熟时间
mature_at = get_mature_at(crop.plant_time, crop.duration, crop.watered_times + 1, seed_config.water_bonus)

# 计算生长阶段
stage = calc_growth_stage(crop.plant_time, crop.duration, crop.watered_times, seed_config.water_bonus)
```

### 离线体力恢复

```python
from app.services.game_engine import restore_stamina

user.stamina = restore_stamina(
    current_stamina=user.stamina,
    last_active=user.last_active_at,
    max_stamina=STAMINA.max_value,
    restore_per_minute=STAMINA.regen_per_min,
)
```

---

## 7. 后续扩展

| 功能 | 方案 | 状态 |
|------|------|------|
| 肥料效果 | 添加 `fertilizer_reduction` 参数 | 待实现 |
| 季节加成 | 添加 `season_modifier` 参数 | 远期规划 |
| 金币奖励计算 | `calc_coin_reward(crop_type, plot_level)` | 待实现 |
