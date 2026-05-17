# GameEngine — 游戏核心规则引擎

> **模块定位**: `app/services/game_engine.py`
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
| **规则集中管理** | 所有游戏核心算法单一来源，避免逻辑分散在各 Service 中 |

---

## 2. 设计决策

### 2.1 纯函数（Pure Function）

本模块所有函数均为纯函数：

| 特性 | 说明 |
|------|------|
| **无副作用** | 不读写数据库，不调用 Repository，不修改全局状态 |
| **输入确定 → 输出确定** | 相同参数始终返回相同结果 |
| **易于测试** | 可直接调用函数，无需 mock 数据库或依赖注入 |
| **线程安全** | 无共享状态，支持并发调用 |

```python
# ✅ 纯函数 — 可直接调用，无需实例化
from app.services.game_engine import is_mature, calc_growth_stage

is_mature(plant_time, grow_time, watered_times, water_bonus)
calc_growth_stage(plant_time, grow_time, watered_times, water_bonus)
```

**对比厚服务**：`FarmService` 等非纯函数模块通过构造函数注入 `db`、`repo` 等依赖，而 `game_engine` 是纯函数集合，零依赖。

### 2.2 时间系统约定

| 约定 | 说明 |
|------|------|
| **时区** | 所有时间使用 UTC（`datetime.now(timezone.utc)`） |
| **存储格式** | SQLite 存储为 `datetime` 对象（UTC） |
| **前端显示** | 前端收到 UTC 时间后转换为本地时区显示 |
| **时间单位** | 作物生长时间以**秒**为单位，体力恢复以**分钟**为单位 |

### 2.3 作物生长算法

采用 **"浇水减时间"** 机制（类似 QQ 农场）：

| 参数 | 说明 |
|------|------|
| `crop_grow_time` | 基础生长时间（秒），不浇水时的完整生长时长 |
| `seed_water_bonus` | 每次浇水减少的生长时间（秒），种子自带加成 |
| `crop_watered_times` | 实际浇水次数 |

```
实际成熟所需时间 = crop_grow_time - crop_watered_times * seed_water_bonus
实际成熟时间 = crop_plant_time + timedelta(seconds=实际成熟所需时间)
```

**边界保护**：实际成熟所需时间不小于基础生长时间的 30%，防止浇水次数过多导致秒熟。

---

## 3. 函数列表

| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `is_mature` | `plant_time`, `grow_time`, `watered_times`, `water_bonus` | `bool` | 作物是否已成熟 |
| `get_mature_at` | `plant_time`, `grow_time`, `watered_times`, `water_bonus` | `datetime` | 作物成熟的具体时间 |
| `calc_growth_stage` | `plant_time`, `grow_time`, `watered_times`, `water_bonus` | `str` | 当前生长阶段 |
| `calc_level_from_xp` | `xp`, `level_table` | `int` | 从经验值计算等级 |
| `restore_stamina` | `current_stamina`, `last_active`, `max_stamina`, `restore_per_minute` | `int` | 离线体力恢复量 |

---

## 4. 函数详解

### 4.1 `is_mature(plant_time, grow_time, watered_times, water_bonus) → bool`

判断作物是否已经成熟。

**业务规则**：
1. 计算实际成熟时间：`plant_time + timedelta(seconds=grow_time - watered_times * water_bonus)`
2. 实际成熟所需时间最小为 `grow_time * 0.3`（防止秒熟）
3. 当前时间 >= 成熟时间 → `True`

```python
is_mature(
    plant_time=datetime(2025, 1, 1, 10, 0, 0),  # 2025-01-01 10:00 UTC
    grow_time=3600,                              # 基础生长时间 3600 秒 = 1 小时
    watered_times=2,                             # 浇水 2 次
    water_bonus=300,                             # 每次浇水减 300 秒
)
# → 实际成熟时间 = 10:00 + (3600 - 2*300)秒 = 10:00 + 3000秒 = 10:50
# → 现在 11:00 >= 10:50 → True（已成熟）
```

---

### 4.2 `get_mature_at(plant_time, grow_time, watered_times, water_bonus) → datetime`

返回作物成熟的绝对时间。

**业务规则**：
1. 计算实际成熟所需时间：`max(grow_time - watered_times * water_bonus, grow_time * 0.3)`
2. 返回：`plant_time + timedelta(seconds=实际成熟所需时间)`

```python
get_mature_at(
    plant_time=datetime(2025, 1, 1, 10, 0, 0),
    grow_time=3600,
    watered_times=2,
    water_bonus=300,
)
# → 10:00 + 3000秒 → datetime(2025, 1, 1, 10, 50, 0)
```

---

### 4.3 `calc_growth_stage(plant_time, grow_time, watered_times, water_bonus) → str`

计算作物当前生长阶段。

**业务规则**：
1. 计算进度百分比：`(now - plant_time) / (grow_time - watered_times * water_bonus)`
2. 进度 < 25% → `"seedling"`（幼苗）
3. 25% <= 进度 < 75% → `"growing"`（生长中）
4. 75% <= 进度 < 100% → `"almost_mature"`（即将成熟）
5. 进度 >= 100% → `"mature"`（已成熟）

```python
calc_growth_stage(
    plant_time=datetime(2025, 1, 1, 10, 0, 0),
    grow_time=3600,
    watered_times=0,
    water_bonus=300,
)
# → 现在 10:30，进度 = 1800/3600 = 50% → "growing"
```

---

### 4.4 `calc_level_from_xp(xp, level_table) → int`

从累计经验值计算当前等级。

**业务规则**：
1. `level_table` 是一个递增整数列表，`level_table[i]` 表示升到第 `i+1` 级所需的最小经验值
2. 找到最大的 `level` 满足 `level_table[level - 1] <= xp`
3. 经验值为 0 → 等级 1

```python
level_table = [0, 100, 300, 600, 1000, 1500]  # 升级所需 XP
calc_level_from_xp(250, level_table)  # 100 <= 250 < 300 → 等级 2
calc_level_from_xp(999, level_table)  # 600 <= 999 < 1000 → 等级 4
calc_level_from_xp(0, level_table)    # → 等级 1
```

---

### 4.5 `restore_stamina(current_stamina, last_active, max_stamina, restore_per_minute) → int`

计算玩家离线期间恢复的体力量。

**业务规则**：
1. 计算离线时长（分钟）：`(now - last_active).total_seconds() / 60`
2. 恢复体力 = `离线时长 * restore_per_minute`
3. 返回：`min(current_stamina + 恢复体力, max_stamina)`

```python
restore_stamina(
    current_stamina=20,           # 剩余 20 体力
    last_active=datetime(2025, 1, 1, 0, 0, 0),  # 上次登录 0:00
    max_stamina=50,               # 最大体力 50
    restore_per_minute=1,         # 每分钟恢复 1 点
)
# → 假设现在 2:30，离线 150 分钟，恢复 150 点
# → min(20 + 150, 50) → 50（已达上限）
```

---

## 5. 实现方案

完整 Python 实现代码：

```python
"""
GameEngine — 游戏核心规则引擎

纯函数集合，封装所有游戏核心计算规则。
不依赖数据库、Repository 或任何外部状态。
"""

from datetime import datetime, timedelta, timezone
from typing import List


def is_mature(
    plant_time: datetime,
    grow_time: int,
    watered_times: int,
    water_bonus: int,
) -> bool:
    """
    判断作物是否已经成熟。

    Args:
        plant_time: 种植时间（UTC）
        grow_time: 基础生长时间（秒）
        watered_times: 浇水次数
        water_bonus: 每次浇水减少的生长时间（秒）

    Returns:
        True 表示作物已成熟
    """
    mature_at = get_mature_at(plant_time, grow_time, watered_times, water_bonus)
    return datetime.now(timezone.utc) >= mature_at


def get_mature_at(
    plant_time: datetime,
    grow_time: int,
    watered_times: int,
    water_bonus: int,
) -> datetime:
    """
    计算作物成熟的绝对时间。

    Args:
        plant_time: 种植时间（UTC）
        grow_time: 基础生长时间（秒）
        watered_times: 浇水次数
        water_bonus: 每次浇水减少的生长时间（秒）

    Returns:
        作物成熟的 datetime 对象（UTC）
    """
    actual_time = grow_time - watered_times * water_bonus
    actual_time = max(actual_time, int(grow_time * 0.3))  # 最小 30%
    return plant_time + timedelta(seconds=actual_time)


def calc_growth_stage(
    plant_time: datetime,
    grow_time: int,
    watered_times: int,
    water_bonus: int,
) -> str:
    """
    计算作物当前生长阶段。

    Args:
        plant_time: 种植时间（UTC）
        grow_time: 基础生长时间（秒）
        watered_times: 浇水次数
        water_bonus: 每次浇水减少的生长时间（秒）

    Returns:
        "seedling" | "growing" | "almost_mature" | "mature"
    """
    actual_time = grow_time - watered_times * water_bonus
    actual_time = max(actual_time, int(grow_time * 0.3))

    elapsed = (datetime.now(timezone.utc) - plant_time).total_seconds()
    progress = elapsed / actual_time if actual_time > 0 else 1.0

    if progress >= 1.0:
        return "mature"
    elif progress >= 0.75:
        return "almost_mature"
    elif progress >= 0.25:
        return "growing"
    else:
        return "seedling"


def calc_level_from_xp(xp: int, level_table: List[int]) -> int:
    """
    从累计经验值计算当前等级。

    Args:
        xp: 累计经验值
        level_table: 升级所需 XP 表，level_table[i] 表示升到第 i+1 级所需 XP

    Returns:
        当前等级（从 1 开始）
    """
    if xp < 0:
        return 1

    level = 1
    for i, required_xp in enumerate(level_table):
        if xp < required_xp:
            return level
        level = i + 2

    return len(level_table)


def restore_stamina(
    current_stamina: int,
    last_active: datetime,
    max_stamina: int,
    restore_per_minute: int,
) -> int:
    """
    计算离线期间恢复的体力量。

    Args:
        current_stamina: 当前剩余体力
        last_active: 上次活跃时间（UTC）
        max_stamina: 最大体力上限
        restore_per_minute: 每分钟恢复的体力量

    Returns:
        恢复后的体力值（不超过上限）
    """
    elapsed_minutes = (datetime.now(timezone.utc) - last_active).total_seconds() / 60
    restored = elapsed_minutes * restore_per_minute
    return min(current_stamina + int(restored), max_stamina)
```

---

## 6. 使用方式

### 6.1 FarmService 中的调用

`FarmService` 在游戏操作（种植、浇水、收获）中调用 `game_engine` 的纯函数：

```python
# app/services/farm_service.py
from app.services.game_engine import is_mature, calc_growth_stage, restore_stamina

class FarmService:
    def __init__(self, db: AsyncSession, user_repo: UserRepository, farm_repo: FarmRepository):
        self.db = db
        self.user_repo = user_repo
        self.farm_repo = farm_repo

    async def water_plot(self, user_id: int, plot_index: int) -> dict:
        """浇水操作"""
        # 1. 检查体力
        user = await self.user_repo.get_by_id(user_id)
        if user.stamina <= 0:
            raise AppValidationError("体力不足")

        # 2. 获取地块上的作物
        plot = await self.farm_repo.get_by_user_and_index(user_id, plot_index)
        if not plot or not plot.crop_type:
            raise AppValidationError("地块上没有作物")

        # 3. 更新浇水次数
        plot.crop_watered_times += 1
        await self.db.commit()

        # 4. 使用 game_engine 计算当前状态（纯函数，无副作用）
        stage = calc_growth_stage(
            plot.crop_plant_time,
            plot.crop_grow_time,
            plot.crop_watered_times,
            plot.crop_seed_water_bonus,
        )

        return {"stage": stage, "mature_at": get_mature_at(...)}

    async def harvest_plot(self, user_id: int, plot_index: int) -> dict:
        """收获操作"""
        # 1. 检查作物是否成熟（纯函数）
        plot = await self.farm_repo.get_by_user_and_index(user_id, plot_index)
        if not is_mature(
            plot.crop_plant_time,
            plot.crop_grow_time,
            plot.crop_watered_times,
            plot.crop_seed_water_bonus,
        ):
            raise AppValidationError("作物尚未成熟")

        # 2. 收获逻辑...
```

### 6.2 离线体力恢复

在用户登录时调用 `restore_stamina`：

```python
# app/services/auth_service.py (login 流程中)
from app.services.game_engine import restore_stamina

async def login(self, username: str, password: str) -> Session:
    user = await self.user_repo.get_by_username(username)
    # ... 密码验证 ...

    # 离线体力恢复（纯函数调用）
    new_stamina = restore_stamina(
        current_stamina=user.stamina,
        last_active=user.last_active,
        max_stamina=user.max_stamina,
        restore_per_minute=1,  # 配置或硬编码
    )
    if new_stamina > user.stamina:
        user.stamina = new_stamina
        user.last_active = datetime.now(timezone.utc)
        await self.db.commit()

    # ... 创建 Session ...
```

---

## 7. 测试策略

由于所有函数都是纯函数，测试非常直接：

```python
# tests/test_game_engine.py
import pytest
from datetime import datetime, timezone, timedelta
from app.services.game_engine import (
    is_mature,
    get_mature_at,
    calc_growth_stage,
    calc_level_from_xp,
    restore_stamina,
)


def test_is_mature():
    plant_time = datetime.now(timezone.utc) - timedelta(hours=2)
    assert is_mature(plant_time, 3600, 0, 0) is True   # 已过 2 小时


def test_get_mature_at():
    plant_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    mature = get_mature_at(plant_time, 3600, 2, 300)
    assert mature == datetime(2025, 1, 1, 10, 50, 0, tzinfo=timezone.utc)


def test_calc_growth_stage():
    plant_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    stage = calc_growth_stage(plant_time, 3600, 0, 0)
    assert stage == "growing"  # 50% 进度


def test_calc_level_from_xp():
    level_table = [0, 100, 300, 600, 1000]
    assert calc_level_from_xp(50, level_table) == 1
    assert calc_level_from_xp(150, level_table) == 2
    assert calc_level_from_xp(999, level_table) == 4


def test_restore_stamina():
    last_active = datetime.now(timezone.utc) - timedelta(hours=2)
    result = restore_stamina(20, last_active, 50, 1)
    assert result == 50  # 120 分钟 * 1 = 120, min(20 + 120, 50) = 50
```

---

## 8. 后续扩展

| 功能 | 方案 | 状态 |
|------|------|------|
| **特殊作物加成** | 添加 `special_bonus` 参数支持不同作物不同浇水加成 | 待实现 |
| **季节加成** | 添加 `season_modifier` 参数，季节影响生长时间 | 远期规划 |
| **肥料效果** | 添加 `fertilizer_reduction` 参数，使用肥料减少生长时间 | 待实现 |
| **经验值奖励计算** | `calc_xp_reward(crop_type, plot_level)` — 收获时计算获得 XP | 待实现 |
| **金币奖励计算** | `calc_coin_reward(crop_type, plot_level)` — 收获时计算获得金币 | 待实现 |

---

## 9. 相关文档

| 文档 | 路径 | 关系 |
|------|------|------|
| FarmService | `docs/services/farm_service.md` | 调用 game_engine 的核心 Service |
| AuthService | `docs/services/auth_service.md` | 登录时调用 `restore_stamina` |
| 配置管理 | `docs/p0/core/config.md` | 生长时间、体力恢复速率等配置 |
| 等级表配置 | `docs/services/farm_service.md` | `level_table` 数据来源 |
