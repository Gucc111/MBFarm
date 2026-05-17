"""
GameEngine — 游戏核心规则引擎

纯函数集合，封装所有游戏核心计算规则。
不依赖数据库、Repository 或任何外部状态。
"""

from datetime import datetime, timedelta, timezone


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


def calc_level_from_xp(xp: int) -> int:
    """
    从累计经验值计算当前等级。

    使用 ``app.core.constants`` 中的 ``LEVEL_XP_THRESHOLD`` 表。

    Args:
        xp: 累计经验值

    Returns:
        当前等级（从 1 开始）
    """
    from app.core.constants import LEVEL_XP_THRESHOLD

    if xp < 0:
        return 1

    level = 1
    for i in range(1, len(LEVEL_XP_THRESHOLD)):
        if xp >= LEVEL_XP_THRESHOLD[i]:
            level = i + 1  # 1-based
        else:
            break
    return level


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
