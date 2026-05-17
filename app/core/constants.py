"""MB Farm 游戏常量定义。

所有游戏平衡参数（作物属性、体力规则、经验曲线等）集中在此管理。
"""

from dataclasses import dataclass
from typing import Final


# ──────────────────────────────────────────────────────────────────────────────
# 种子/作物配置
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SeedConfig:
    """作物种子配置"""
    id: str
    name: str
    buy_price: int
    sell_price: int
    grow_time: int       # 秒
    xp_reward: int
    unlock_level: int
    water_bonus: int     # 秒


SEEDS: Final[tuple[SeedConfig, ...]] = (
    SeedConfig(
        id="wheat", name="小麦", buy_price=10, sell_price=18,
        grow_time=30 * 60, xp_reward=5, unlock_level=1, water_bonus=5 * 60,
    ),
    SeedConfig(
        id="carrot", name="胡萝卜", buy_price=30, sell_price=55,
        grow_time=2 * 60 * 60, xp_reward=15, unlock_level=2, water_bonus=15 * 60,
    ),
    SeedConfig(
        id="tomato", name="番茄", buy_price=80, sell_price=150,
        grow_time=6 * 60 * 60, xp_reward=40, unlock_level=3, water_bonus=30 * 60,
    ),
    SeedConfig(
        id="strawberry", name="草莓", buy_price=200, sell_price=400,
        grow_time=12 * 60 * 60, xp_reward=100, unlock_level=5, water_bonus=60 * 60,
    ),
    SeedConfig(
        id="sunflower", name="向日葵", buy_price=500, sell_price=1000,
        grow_time=24 * 60 * 60, xp_reward=250, unlock_level=8, water_bonus=90 * 60,
    ),
)

# 便捷查找：按 id 索引
SEED_MAP: Final[dict[str, SeedConfig]] = {s.id: s for s in SEEDS}


# ──────────────────────────────────────────────────────────────────────────────
# 体力配置
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class StaminaConfig:
    """体力配置"""
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


# ──────────────────────────────────────────────────────────────────────────────
# 等级经验表
# ──────────────────────────────────────────────────────────────────────────────

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
    """根据累计经验值计算当前等级（1-based）。

    LEVEL_XP_THRESHOLD[i] 表示达到 i+1 级所需的累计经验值。
    例: xp=0 → 1级, xp=100 → 2级, xp=999 → 5级
    """
    level = 1  # 最低 1 级
    for i in range(1, len(LEVEL_XP_THRESHOLD)):
        if xp >= LEVEL_XP_THRESHOLD[i]:
            level = i + 1  # 1-based
        else:
            break
    return level


def xp_for_next_level(level: int) -> int:
    """获取升到下一级所需经验。

    参数 level 为 1-based 等级（1=1级, 2=2级, ...）。
    返回从当前等级到下一级所需的经验值差。
    满级时返回 0。
    """
    idx = level - 1  # 转为 0-based 索引
    current = LEVEL_XP_THRESHOLD[min(idx, MAX_LEVEL)]
    next_threshold = LEVEL_XP_THRESHOLD[min(idx + 1, MAX_LEVEL)]
    return next_threshold - current


# ──────────────────────────────────────────────────────────────────────────────
# 用户初始值
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class InitUserConfig:
    """新用户初始属性"""
    gold: int
    stamina: int
    level: int
    xp: int


INIT_USER: Final[InitUserConfig] = InitUserConfig(
    gold=500,
    stamina=100,
    level=1,
    xp=0,
)


# ──────────────────────────────────────────────────────────────────────────────
# 地块配置
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class FarmConfig:
    """地块/农场配置"""
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


# ──────────────────────────────────────────────────────────────────────────────
# 其他系统常量
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SystemConfig:
    """其他系统常量"""
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
