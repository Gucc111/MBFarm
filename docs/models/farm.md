# Farm Data Models — Plot & Crop

> **模块**: `app/models/farm.py`  
> **数据源**: SQLite 数据库  
> **ORM**: SQLAlchemy 2.0 (异步)

---

## 1. 模块职责

`farm` 模块负责管理农场核心游戏实体：

- **Plot（地块）**：玩家耕作的物理地块，持久存在。一个玩家拥有多个地块，每个地块在同一时刻只能种植一种作物。
- **Crop（作物）**：单次种植的生命周期记录，从种植到收获（或枯萎）。

---

## 2. 设计决策

### 2.1 Plot ↔ Crop 分离

**为什么将 Plot 和 Crop 分开？**

- **Plot 是持久实体**：地块是玩家的资产，永久存在（除非手动删除）。它代表"一块可以种植的土地"。
- **Crop 是生命周期实体**：每次种植产生一个新的 Crop 记录。收获后 Crop 记录保留（标记 `is_harvested=True`），便于数据统计和回溯。
- **解耦种植逻辑**：Plot 只需知道"当前种了什么"，具体生长规则由 Crop 承载。

```
User (1) ──< Plot (N) ──< Crop (1)
                  当前作物     历史作物（is_harvested=True）
```

### 2.2 实时成熟判断 vs 后台任务

**选择：实时计算，非后台更新。**

成熟判断公式（实时计算）：

```python
from datetime import datetime, timedelta

def is_mature(crop: Crop, watered_times: int) -> bool:
    remaining_seconds = crop.duration - watered_times * water_bonus
    return datetime.utcnow() >= crop.plant_time + timedelta(seconds=remaining_seconds)
```

**理由：**
1. 小型项目（十几人），并发量极低，实时计算无性能压力
2. 避免后台定时任务的复杂度和故障点
3. 浇水后状态即时生效，用户体验更好
4. 数据一致性无需额外保障

### 2.3 Crop 记录保留而非删除

收获后 Crop 记录保留，标记 `is_harvested=True`：
- 用于统计玩家的收获总量、种植历史
- 避免数据库记录频繁删除/插入
- 便于未来实现"最近收获记录"等社交功能

---

## 3. SQL DDL

### 3.1 plots 表

```sql
CREATE TABLE plots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    index       INTEGER NOT NULL,
    level       INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 5),
    crop_id     INTEGER REFERENCES crops(id),
    watered_times INTEGER NOT NULL DEFAULT 0,
    planted_at  TIMESTAMP,
    last_watered_at TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT (datetime('now')),

    UNIQUE(user_id, index)
);

CREATE INDEX idx_plots_user_id ON plots(user_id);
CREATE INDEX idx_plots_crop_id ON plots(crop_id);
```

### 3.2 crops 表

```sql
CREATE TABLE crops (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_id         INTEGER NOT NULL REFERENCES plots(id),
    seed_type       VARCHAR(32) NOT NULL,
    plant_time      TIMESTAMP NOT NULL,
    duration        INTEGER NOT NULL,
    watered_times   INTEGER NOT NULL DEFAULT 0,
    is_harvested    BOOLEAN NOT NULL DEFAULT 0,
    created_at      TIMESTAMP NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (plot_id) REFERENCES plots(id) ON DELETE CASCADE
);

CREATE INDEX idx_crops_plot_id ON crops(plot_id);
CREATE INDEX idx_crops_seed_type ON crops(seed_type);
CREATE INDEX idx_crops_is_harvested ON crops(is_harvested);
```

---

## 4. Plot 模型字段说明

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `Integer` | PK, 自增 | 主键 |
| `user_id` | `Integer` | FK → `users.id`, NOT NULL | 所属用户 |
| `index` | `Integer` | NOT NULL | 地块索引 (0, 1, 2, ...) |
| `level` | `Integer` | NOT NULL, DEFAULT 1, CHECK (1-5) | 地块等级，影响浇水效率 |
| `crop_id` | `Integer` | FK → `crops.id`, nullable | 当前活跃作物 ID |
| `watered_times` | `Integer` | NOT NULL, DEFAULT 0 | 当前作物的累计浇水次数 |
| `planted_at` | `DateTime` | nullable | 当前作物种植时间 |
| `last_watered_at` | `DateTime` | nullable | 上次浇水时间 |
| `updated_at` | `DateTime` | NOT NULL | 记录更新时间 |

**唯一约束**: `(user_id, index)` — 同一用户的每个地块索引唯一。

---

## 5. Crop 模型字段说明

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `Integer` | PK, 自增 | 主键 |
| `plot_id` | `Integer` | FK → `plots.id`, NOT NULL | 所属地块 |
| `seed_type` | `String(32)` | NOT NULL | 种子类型（如 `wheat`, `carrot`, `tomato`） |
| `plant_time` | `DateTime` | NOT NULL | 种植时间（UTC） |
| `duration` | `Integer` | NOT NULL | 基础成长时间（秒），种植时从 `SeedConfig` 复制 |
| `watered_times` | `Integer` | NOT NULL, DEFAULT 0 | 累计浇水次数 |
| `is_harvested` | `Boolean` | NOT NULL, DEFAULT False | 是否已收获 |
| `created_at` | `DateTime` | NOT NULL | 创建时间 |

**成熟判断**：
```
剩余秒数 = duration - watered_times × water_bonus
成熟条件: utcnow() >= plant_time + timedelta(seconds=剩余秒数)

其中 water_bonus 来自 constants.SEEDS[seed_type].water_bonus
```

---

## 6. 关系说明

```
User (1) ──< Plot (N)
    │              │
    │              └──< Crop (N)
    │                    每个 Plot 同一时刻最多一个活跃 Crop
    │
    └──< Session (N)
```

- **User → Plot**: 一对多，一个用户拥有多个地块
- **Plot → Crop**: 一对多，一个地块可多次种植（收获后产生新 Crop）
- **Plot.crop_id**: 外键指向当前活跃 Crop（nullable，空地时为 NULL）
- **Cascade delete**: Crop 随 Plot 删除而删除 (`ON DELETE CASCADE`)

---

## 7. 完整 Python 实现代码

```python
"""
Farm data models: Plot and Crop.

Plot: A physical farming plot owned by a user.
Crop: A single planting lifecycle on a plot.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    selectinload,
)

from app.core.database import Base


# ---------------------------------------------------------------------------
# 模型基类
# ---------------------------------------------------------------------------

class FarmBase(Base):
    __abstract__ = True

    @staticmethod
    def _utcnow() -> datetime:
        """返回 UTC 当前时间。"""
        return datetime.utcnow()


# ---------------------------------------------------------------------------
# Plot（地块）
# ---------------------------------------------------------------------------

class Plot(FarmBase):
    """
    玩家的一块耕地。

    一个玩家拥有多个 Plot（通过 index 区分）。
    每个 Plot 在任意时刻最多关联一个活跃的 Crop（通过 crop_id 指向）。
    """

    __tablename__ = "plots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    crop_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("crops.id", ondelete="SET NULL")
    )
    watered_times: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    planted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_watered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.datetime("now")
    )

    # 关系
    user = relationship("User", back_populates="plots", lazy="select")
    current_crop = relationship(
        "Crop", back_populates="plot", lazy="selectin"
    )

    # 约束
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 5", name="chk_plots_level"),
        {"sqlite_autoincrement": True},
    )

    # ------------------------------------------------------------------
    # 实例方法
    # ------------------------------------------------------------------

    def has_crop(self) -> bool:
        """地块是否有当前作物。"""
        return self.crop_id is not None

    def plant(
        self,
        seed_type: str,
        duration: int,
        water_bonus: int,
        plant_time: Optional[datetime] = None,
    ) -> "Crop":
        """
        在空地块上种植作物。

        Args:
            seed_type:     种子类型 (如 "wheat")
            duration:      基础成长时间（秒）
            water_bonus:   每次浇水减少的秒数
            plant_time:    种植时间，默认 utcnow()

        Returns:
            新创建的 Crop 对象（尚未持久化）
        """
        now = plant_time or self._utcnow()
        crop = Crop(
            plot_id=self.id,
            seed_type=seed_type,
            plant_time=now,
            duration=duration,
            watered_times=0,
            is_harvested=False,
        )
        self.crop_id = crop.id
        self.watered_times = 0
        self.planted_at = now
        self.last_watered_at = None
        self.updated_at = self._utcnow()
        return crop

    def water(self, water_bonus: int, now: Optional[datetime] = None) -> None:
        """
        浇水。

        Args:
            water_bonus: 本次浇水减少的成长秒数
            now:         当前时间，默认 utcnow()
        """
        self.watered_times += 1
        self.last_watered_at = now or self._utcnow()
        self.updated_at = self._utcnow()

    def harvest(self) -> bool:
        """
        收获当前作物。

        Returns:
            True 如果成功收获，False 如果地块上没有作物
        """
        if not self.has_crop() or not self.current_crop:
            return False

        # 检查是否成熟
        if not self.current_crop.is_mature(self.watered_times):
            return False

        self.current_crop.is_harvested = True
        self.crop_id = None
        self.watered_times = 0
        self.planted_at = None
        self.last_watered_at = None
        self.updated_at = self._utcnow()
        return True

    def get_remaining_seconds(self, water_bonus: int) -> Optional[int]:
        """
        获取作物剩余成长秒数。

        Returns:
            剩余秒数（>=0 表示已成熟），None 如果地块上没有作物
        """
        if not self.current_crop:
            return None
        remaining = self.current_crop.duration - self.watered_times * water_bonus
        return max(0, remaining)

    def is_mature(self, water_bonus: int) -> Optional[bool]:
        """
        检查作物是否已成熟。

        Returns:
            True/False 或 None（无作物）
        """
        remaining = self.get_remaining_seconds(water_bonus)
        if remaining is None:
            return None
        # remaining <= 0 表示时间已耗尽（已成熟）
        return remaining <= 0


# ---------------------------------------------------------------------------
# Crop（作物）
# ---------------------------------------------------------------------------

class Crop(FarmBase):
    """
    单次种植的生命周期记录。

    从种植到收获（或枯萎），一条 Crop 记录代表一次完整的种植过程。
    收获后记录保留（is_harvested=True），用于数据统计。
    """

    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plots.id", ondelete="CASCADE"), nullable=False
    )
    seed_type: Mapped[str] = mapped_column(String(32), nullable=False)
    plant_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    watered_times: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    is_harvested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.datetime("now")
    )

    # 关系
    plot = relationship("Plot", back_populates="current_crop", lazy="select")

    # ------------------------------------------------------------------
    # 实例方法
    # ------------------------------------------------------------------

    def is_mature(self, watered_times: int, water_bonus: int) -> bool:
        """
        判断作物是否成熟（考虑浇水加成）。

        公式:
            remaining = duration - watered_times × water_bonus
            mature if (utcnow() - plant_time).total_seconds() >= remaining

        Args:
            watered_times: 已浇水次数
            water_bonus:   每次浇水减少的秒数

        Returns:
            True 如果已成熟
        """
        from datetime import datetime as _datetime

        remaining_seconds = self.duration - watered_times * water_bonus
        elapsed = (_datetime.utcnow() - self.plant_time).total_seconds()
        return elapsed >= max(0, remaining_seconds)

    @property
    def progress(self) -> float:
        """
        作物成长进度百分比 (0.0 ~ 1.0+)。

        Returns:
            进度值，可能 > 1.0 表示已成熟
        """
        from datetime import datetime as _datetime

        remaining_seconds = self.duration - self.watered_times * 2  # 默认 water_bonus=2
        elapsed = (_datetime.utcnow() - self.plant_time).total_seconds()
        if remaining_seconds <= 0:
            return 1.0
        return min(1.0, elapsed / remaining_seconds)
```

---

## 8. 使用示例

### 8.1 查询用户所有地块（含当前作物）

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# 查询用户 1 的所有地块，预加载当前作物
stmt = (
    select(Plot)
    .where(Plot.user_id == user_id)
    .options(selectinload(Plot.current_crop))
)
result = await session.execute(stmt)
plots = result.scalars().all()

for plot in plots:
    if plot.has_crop() and plot.current_crop:
        crop = plot.current_crop
        print(f"地块 {plot.index}: {crop.seed_type} - "
              f"进度 {crop.progress:.0%}")
    else:
        print(f"地块 {plot.index}: 空闲")
```

### 8.2 种植作物

```python
from app.models.farm import Plot
from app.constants import SEEDS  # {seed_type: {duration, water_bonus}}

# 假设已找到 index=0 的空地块
plot: Plot = ...

seed_type = "wheat"
config = SEEDS[seed_type]  # {duration: 60, water_bonus: 2}

new_crop = plot.plant(
    seed_type=seed_type,
    duration=config["duration"],
    water_bonus=config["water_bonus"],
)

await session.add(new_crop)
await session.commit()
```

### 8.3 浇水

```python
from datetime import datetime as dt

plot: Plot = ...
seed_type = plot.current_crop.seed_type
config = SEEDS[seed_type]

plot.water(water_bonus=config["water_bonus"], now=dt.utcnow())
await session.commit()
```

### 8.4 收获

```python
plot: Plot = ...
config = SEEDS[plot.current_crop.seed_type]

if plot.is_mature(config["water_bonus"]):
    success = plot.harvest()
    if success:
        await session.commit()
        print("收获成功！")
    else:
        print("作物尚未成熟")
else:
    remaining = plot.get_remaining_seconds(config["water_bonus"])
    print(f"还需等待 {remaining} 秒")
```

### 8.5 查询用户收获历史

```python
from sqlalchemy import select
from app.models.farm import Crop

# 查询用户所有已收获的作物（按时间倒序）
stmt = (
    select(Crop)
    .join(Plot)
    .where(
        Plot.user_id == user_id,
        Crop.is_harvested == True,
    )
    .order_by(Crop.created_at.desc())
    .options(selectinload(Crop.plot))
)
result = await session.execute(stmt)
harvested = result.scalars().all()

for crop in harvested:
    print(f"{crop.seed_type} @ plot {crop.plot.index} "
          f"({crop.created_at})")
```

---

## 9. 与常量配置的关系

Crop 的 `duration` 和 `water_bonus` 在种植时从 `constants.SEEDS` 配置中读取：

```python
# constants.py
SEEDS = {
    "wheat":     {"duration": 300, "water_bonus": 2, "sell_price": 5},
    "carrot":    {"duration": 600, "water_bonus": 3, "sell_price": 10},
    "tomato":    {"duration": 900, "water_bonus": 4, "sell_price": 20},
}
```

这些值**存入 Crop.duration**，而不是每次都查配置。理由：
- 种植时固化值，后续即使修改种子配置不影响已有作物
- 避免数据库查询，成熟判断更快速
- 便于历史记录追溯（即使种子被删除，收获记录仍可解释）

---

## 10. 索引策略

| 表 | 索引 | 用途 |
|----|------|------|
| plots | PRIMARY KEY (id) | 主键查询 |
| plots | UNIQUE (user_id, index) | 防止重复地块 |
| plots | INDEX (user_id) | 查询用户所有地块 |
| plots | INDEX (crop_id) | 反向查找作物所属地块 |
| crops | PRIMARY KEY (id) | 主键查询 |
| crops | INDEX (plot_id) | 查询地块的种植历史 |
| crops | INDEX (seed_type) | 按种子类型统计 |
| crops | INDEX (is_harvested) | 快速过滤已收获记录 |

---

## 11. 扩展预留

| 方向 | 预留设计 |
|------|----------|
| 肥料/道具 | 在 Crop 上增加 `bonus_seconds` 字段（类似 water_bonus 但一次性） |
| 枯萎机制 | 增加 `withered_at` 字段，超过 `duration + grace_period` 未收获自动标记枯萎 |
| 地块解锁 | `level` 字段已预留，未来可随用户等级提升解锁更多/更高级地块 |
| 社交偷菜 | Crop 表已含 `seed_type` 和 `plant_time`，可用于计算可偷时机 |

---

## 12. 数据流图

```
用户操作          Plot                        Crop
  │              ┌────────┐                  ┌──────────┐
  │  ──种植──▶  │  Plot  │                  │  Crop    │
  │             │  id=N  │◀─────────────────│  plot_id │
  │  ──浇水──▶  │  water │                  │  water   │
  │             │  plant │                  │  plant   │
  │             └───┬────┘                  └──────────┘
  │                 │                          │
  │  ──收获──▶  检查成熟                      │
  │             │  标记 harvested             │
  │             │  crop_id=NULL               │
  └───────────────┼──────────────────────────┘
                  │
            数据持久化 (SQLite)
```

---

*文档版本: 1.0 | 创建时间: 2025-07-13*
