# 游戏常量模块 (app/core/constants.py)

## 模块职责

定义 MB Farm 游戏中所有硬编码常量，包括：
- 种子/作物配置
- 体力配置
- 等级经验阈值
- 用户初始值
- 地块配置
- 其他系统常量

## 设计决策

### 为什么独立常量模块？
1. **单一真相源 (Single Source of Truth)**：游戏平衡参数集中管理，避免分散在各处硬编码。
2. **类型安全**：使用 `frozen dataclass` + `TypedDict`，IDE 可自动补全，编译期检查。
3. **不可变性**：`frozen=True` 防止运行时意外修改常量。

### dataclass vs 枚举 vs DB 表
- **不用枚举**：枚举不支持附加字段（如 buy_price, grow_time），dataclass 更合适。
- **初期不存 DB**：作物参数属于游戏策划数据，频繁修改才需要 DB 存储。初期用代码常量即可。
- **可扩展**：后续可从 DB 加载覆盖代码默认值，接口不变。

## 常量组详解

### 1. 种子/作物配置 (SEEDS)

```python
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class SeedConfig:
    """作物种子配置"""
    id: str                    # 唯一标识符
    name: str                  # 作物名称（显示用）
    buy_price: int            # 购买价格（金币）
    sell_price: int           # 收获出售价格（金币）
    grow_time: int            # 生长时间（秒）
    xp_reward: int            # 收获获得经验值
    unlock_level: int         # 解锁所需用户等级
    water_bonus: int          # 浇水后减少的生长时间（秒）


SEEDS: Final[tuple[SeedConfig, ...]] = (
    SeedConfig(
        id="wheat",
        name="小麦",
        buy_price=10,
        sell_price=18,
        grow_time=30 * 60,      # 30 分钟
        xp_reward=5,
        unlock_level=1,
        water_bonus=5 * 60,     # 浇水减少 5 分钟
    ),
    SeedConfig(
        id="carrot",
        name="胡萝卜",
        buy_price=30,
        sell_price=55,
        grow_time=2 * 60 * 60,  # 2 小时
        xp_reward=15,
        unlock_level=2,
        water_bonus=15 * 60,    # 浇水减少 15 分钟
    ),
    SeedConfig(
        id="tomato",
        name="番茄",
        buy_price=80,
        sell_price=150,
        grow_time=6 * 60 * 60,  # 6 小时
        xp_reward=40,
        unlock_level=3,
        water_bonus=30 * 60,    # 浇水减少 30 分钟
    ),
    SeedConfig(
        id="strawberry",
        name="草莓",
        buy_price=200,
        sell_price=400,
        grow_time=12 * 60 * 60, # 12 小时
        xp_reward=100,
        unlock_level=5,
        water_bonus=60 * 60,    # 浇水减少 1 小时
    ),
    SeedConfig(
        id="sunflower",
        name="向日葵",
        buy_price=500,
        sell_price=1000,
        grow_time=24 * 60 * 60, # 24 小时
        xp_reward=250,
        unlock_level=8,
        water_bonus=90 * 60,    # 浇水减少 1.5 小时
    ),
)

# 便捷查找：按 id 索引
SEED_MAP: Final[dict[str, SeedConfig]] = {s.id: s for s in SEEDS}
```

| 作物     | 买价 | 卖价 | 利润 | 利润/分钟 | 成长时间 | XP | 解锁等级 | 浇水奖励 |
|----------|------|------|------|-----------|----------|-----|----------|----------|
| 小麦     | 10   | 18   | 8    | 0.16      | 30分钟   | 5   | 1        | 5分钟    |
| 胡萝卜   | 30   | 55   | 25   | 0.21      | 2小时    | 15  | 2        | 15分钟   |
| 番茄     | 80   | 150  | 70   | 0.19      | 6小时    | 40  | 3        | 30分钟   |
| 草莓     | 200  | 400  | 200  | 0.28      | 12小时   | 100 | 5        | 1小时    |
| 向日葵   | 500  | 1000 | 500  | 0.35      | 24小时   | 250 | 8        | 1.5小时  |

### 2. 体力配置 (STAMINA)

```python
@dataclass(frozen=True, slots=True)
class StaminaConfig:
    """体力配置"""
    max_value: int        # 最大体力值
    regen_per_min: int    # 每分钟恢复量
    plant_cost: int       # 种植消耗
    harvest_cost: int     # 收获消耗
    water_cost: int       # 浇水消耗
    steal_cost: int       # 偷菜消耗


STAMINA: Final[StaminaConfig] = StaminaConfig(
    max_value=100,
    regen_per_min=1,          # 每分钟恢复 1 点
    plant_cost=5,             # 种植消耗 5 点
    harvest_cost=3,           # 收获消耗 3 点
    water_cost=2,             # 浇水消耗 2 点
    steal_cost=3,             # 偷菜消耗 3 点
)
```

### 3. 等级经验表 (LEVEL_XP_THRESHOLD)

```python
# 累计经验阈值表（0-indexed: 索引 0 = 1 级, 索引 1 = 2 级, ...）
LEVEL_XP_THRESHOLD: Final[tuple[int, ...]] = (
    0,       # 1 级（初始）
    100,     # 2 级
    300,     # 3 级
    600,     # 4 级
    1000,    # 5 级
    1500,    # 6 级
    2100,    # 7 级
    2800,    # 8 级
    3600,    # 9 级
    4500,    # 10 级
)
MAX_LEVEL: Final[int] = len(LEVEL_XP_THRESHOLD) - 1  # = 10

def get_level_by_xp(xp: int) -> int:
    """根据累计经验值计算当前等级（返回 1-based 等级）。

    LEVEL_XP_THRESHOLD[i] 表示达到 i+1 级所需的累计经验值。
    例: xp=0 → 1级, xp=100 → 2级
    """
    level = 1
    for i in range(1, len(LEVEL_XP_THRESHOLD)):
        if xp >= LEVEL_XP_THRESHOLD[i]:
            level = i + 1
        else:
            break
    return level


def xp_for_next_level(level: int) -> int:
    """获取升到下一级所需经验。

    参数 level 为 1-based 等级（1=1级, 2=2级, ...）。
    满级时返回 0。
    """
    idx = level - 1  # 转为 0-based 索引
    current = LEVEL_XP_THRESHOLD[min(idx, MAX_LEVEL)]
    next_threshold = LEVEL_XP_THRESHOLD[min(idx + 1, MAX_LEVEL)]
    return next_threshold - current
```

等级升级曲线（线性递推）：

| 当前等级 | 升级所需经验 | 累计经验阈值 | 升级所需时间（纯种小麦, 含浇水） |
|----------|-------------|-------------|-------------------------------|
| 1 → 2    | 100         | 100         | ~10 小时                      |
| 2 → 3    | 200         | 300         | ~20 小时                      |
| 3 → 4    | 300         | 600         | ~30 小时                      |
| 4 → 5    | 400         | 1000        | ~42 小时                      |
| 5 → 6    | 500         | 1500        | ~52 小时                      |
| 6 → 7    | 600         | 2100        | ~62 小时                      |
| 7 → 8    | 700         | 2800        | ~72 小时                      |
| 8 → 9    | 800         | 3600        | ~83 小时                      |
| 9 → 10   | 900         | 4500        | ~94 小时                      |

### 4. 用户初始值 (INIT_USER)

```python
@dataclass(frozen=True, slots=True)
class InitUserConfig:
    """新用户初始属性"""
    gold: int           # 初始金币
    stamina: int        # 初始体力
    level: int          # 初始等级
    xp: int             # 初始经验


INIT_USER: Final[InitUserConfig] = InitUserConfig(
    gold=500,           # 500 金币
    stamina=100,        # 满体力
    level=1,            # 1 级
    xp=0,               # 0 经验
)
```

### 5. 地块配置 (FARM_CONFIG)

```python
@dataclass(frozen=True, slots=True)
class FarmConfig:
    """地块/农场配置"""
    initial_plots: int        # 初始地块数量
    max_plots: int            # 最大地块数量
    plot_upgrade_cost: int    # 每级扩展费用（金币）
    max_farm_level: int       # 农场最大等级


FARM: Final[FarmConfig] = FarmConfig(
    initial_plots=9,            # 初始 9 块地
    max_plots=25,               # 最大 25 块地
    plot_upgrade_cost=200,      # 扩展费用 200 金币/级
    max_farm_level=5,           # 农场最大等级 5
)
```

地块扩展方案（每级增加若干地块）：

| 农场等级 | 总地块数 | 新增地块 | 扩展费用 |
|----------|---------|---------|----------|
| 1        | 9       | -       | -        |
| 2        | 12      | +3      | 200      |
| 3        | 16      | +4      | 400      |
| 4        | 20      | +4      | 600      |
| 5        | 25      | +5      | 800      |

### 6. 其他系统常量 (SYSTEM_CONFIG)

```python
@dataclass(frozen=True, slots=True)
class SystemConfig:
    """其他系统常量"""
    max_daily_free_water: int     # 每日免费浇水次数
    max_daily_steal: int          # 每日偷菜次数上限
    max_friends: int              # 好友数量上限
    session_ttl_hours: int        # Session 有效期（小时）


SYSTEM: Final[SystemConfig] = SystemConfig(
    max_daily_free_water=3,       # 每日免费浇水 3 次
    max_daily_steal=3,            # 每日偷菜上限 3 次
    max_friends=50,               # 好友上限 50 人
    session_ttl_hours=24,         # Session 有效期 24 小时
)
```

## 完整模块代码

将以上所有片段整合到 `app/core/constants.py`：

```python
"""
MB Farm 游戏常量定义。

所有游戏平衡参数（作物属性、体力规则、经验曲线等）集中在此管理。
"""

from dataclasses import dataclass
from typing import Final


# ─────────────────────────────────────────────
# 种子/作物配置
# ─────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SeedConfig:
    id: str
    name: str
    buy_price: int
    sell_price: int
    grow_time: int       # 秒
    xp_reward: int
    unlock_level: int
    water_bonus: int     # 秒


SEEDS: Final[tuple[SeedConfig, ...]] = (
    SeedConfig(id="wheat", name="小麦", buy_price=10, sell_price=18, grow_time=1800, xp_reward=5, unlock_level=1, water_bonus=300),
    SeedConfig(id="carrot", name="胡萝卜", buy_price=30, sell_price=55, grow_time=7200, xp_reward=15, unlock_level=2, water_bonus=900),
    SeedConfig(id="tomato", name="番茄", buy_price=80, sell_price=150, grow_time=21600, xp_reward=40, unlock_level=3, water_bonus=1800),
    SeedConfig(id="strawberry", name="草莓", buy_price=200, sell_price=400, grow_time=43200, xp_reward=100, unlock_level=5, water_bonus=3600),
    SeedConfig(id="sunflower", name="向日葵", buy_price=500, sell_price=1000, grow_time=86400, xp_reward=250, unlock_level=8, water_bonus=5400),
)

SEED_MAP: Final[dict[str, SeedConfig]] = {s.id: s for s in SEEDS}


# ─────────────────────────────────────────────
# 体力配置
# ─────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class StaminaConfig:
    max_value: int
    regen_per_min: int
    plant_cost: int
    harvest_cost: int
    water_cost: int
    steal_cost: int


STAMINA: Final[StaminaConfig] = StaminaConfig(
    max_value=100,
    regen_per_min=1,
    plant_cost=5,
    harvest_cost=3,
    water_cost=2,
    steal_cost=3,
)


# ─────────────────────────────────────────────
# 等级经验表
# ─────────────────────────────────────────────

LEVEL_XP_THRESHOLD: Final[tuple[int, ...]] = (
    0,       # 1 级（初始）
    100,     # 2 级
    300,     # 3 级
    600,     # 4 级
    1000,    # 5 级
    1500,    # 6 级
    2100,    # 7 级
    2800,    # 8 级
    3600,    # 9 级
    4500,    # 10 级
)
MAX_LEVEL: Final[int] = len(LEVEL_XP_THRESHOLD) - 1  # = 10


def get_level_by_xp(xp: int) -> int:
    """根据累计经验值计算当前等级（返回 1-based 等级）"""
    level = 1
    for i in range(1, len(LEVEL_XP_THRESHOLD)):
        if xp >= LEVEL_XP_THRESHOLD[i]:
            level = i + 1
        else:
            break
    return level


def xp_for_next_level(level: int) -> int:
    """获取升到下一级所需经验（level 为 1-based，满级返回 0）"""
    idx = level - 1
    current = LEVEL_XP_THRESHOLD[min(idx, MAX_LEVEL)]
    next_threshold = LEVEL_XP_THRESHOLD[min(idx + 1, MAX_LEVEL)]
    return next_threshold - current


# ─────────────────────────────────────────────
# 用户初始值
# ─────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class InitUserConfig:
    gold: int
    stamina: int
    level: int
    xp: int


INIT_USER: Final[InitUserConfig] = InitUserConfig(
    gold=500, stamina=100, level=1, xp=0,
)


# ─────────────────────────────────────────────
# 地块配置
# ─────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class FarmConfig:
    initial_plots: int
    max_plots: int
    plot_upgrade_cost: int
    max_farm_level: int


FARM: Final[FarmConfig] = FarmConfig(
    initial_plots=9,
    max_plots=25,
    plot_upgrade_cost=200,
    max_farm_level=5,
)


# ─────────────────────────────────────────────
# 其他系统常量
# ─────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SystemConfig:
    max_daily_free_water: int
    max_daily_steal: int
    max_friends: int
    session_ttl_hours: int


SYSTEM: Final[SystemConfig] = SystemConfig(
    max_daily_free_water=3,
    max_daily_steal=3,
    max_friends=50,
    session_ttl_hours=24,
)
```

## 使用方式示例

```python
from app.core.constants import SEED_MAP, STAMINA, get_level_by_xp

# 查找小麦信息
wheat = SEED_MAP["wheat"]
print(f"小麦售价: {wheat.sell_price}, 生长时间: {wheat.grow_time}s")

# 体力检查
if stamina >= STAMINA.plant_cost:
    print("可以种植")

# 经验等级计算
level = get_level_by_xp(350)  # 返回 3（因为 300 <= 350 < 600）
```

## 后续扩展

### 从数据库加载常量

当游戏上线后，策划可能随时调整平衡参数，此时可将常量表迁移到数据库：

```python
class SeedConfigDB(Base):
    __tablename__ = "seed_configs"
    id = Column(String, primary_key=True)
    name = Column(String)
    buy_price = Column(Integer)
    # ... 其他字段

class ConstantLoader:
    """加载器：优先从 DB 加载，不存在则回退到代码常量"""
    _cache: dict[str, Any] = {}

    @classmethod
    def get_seed(cls, seed_id: str) -> SeedConfig:
        db_config = cls._cache.get(seed_id)
        if db_config:
            return db_config
        # 回退到代码常量
        return SEED_MAP[seed_id]
```

### 热重载

配合文件监听或 WebSocket 广播，实现常量热更新，无需重启服务器。
