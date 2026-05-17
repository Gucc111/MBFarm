# Farm Data Models — Plot & Crop

> **模块**: `app/models/farm.py`  
> **数据源**: SQLite 数据库  
> **ORM**: SQLAlchemy 2.0 (异步)

---

## 1. 模块职责

`farm` 模块负责管理农场核心游戏实体：

- **Plot（地块）**：玩家耕作的物理地块，持久存在。一个玩家拥有多个地块，每个地块在同一时刻只能种植一种作物。
- **Crop（作物）**：单次种植的生命周期记录，从种植到收获（或枯萎）。

### 模型设计理念：薄模型（Thin Model）

模型层**仅定义数据库 schema**（字段、约束、关系），不包含业务逻辑。业务规则由 `services/` 和 `repositories/` 层承载。成熟判断等计算委托给 `game_engine` 纯函数。

---

## 2. 设计决策

### 2.1 Plot ↔ Crop 分离

- **Plot 是持久实体**：地块是玩家的资产，永久存在。它代表"一块可以种植的土地"。
- **Crop 是生命周期实体**：每次种植产生一个新的 Crop 记录。收获后 Crop 标记 `is_harvested=True`，便于数据统计。
- **解耦种植逻辑**：Plot 只需知道"当前种了什么"（`crop_id`），具体生长规则由 Crop + game_engine 承载。

```
User (1) ──< Plot (N) ──< Crop (1)
                  当前作物     历史作物（is_harvested=True）
```

### 2.2 实时成熟判断

成熟判断公式在 `game_engine.is_mature()` 中实时计算，不使用后台任务：

```python
actual_time = duration - watered_times * water_bonus
actual_time = max(actual_time, int(duration * 0.3))  # 最小 30%
mature = (now_utc) >= (plant_time + timedelta(seconds=actual_time))
```

**理由：**
1. 小型项目（十几人），并发量极低，实时计算无性能压力
2. 避免后台定时任务的复杂度和故障点
3. 浇水后状态即时生效，用户体验更好

### 2.3 地块索引（1-based）

`Plot.index` 从 **1 开始**（1, 2, 3, ...），与前端展示顺序一致。新用户初始获得 `FARM.initial_plots`（9）块地。

---

## 3. SQL DDL

### 3.1 plots 表

```sql
CREATE TABLE plots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    index           INTEGER NOT NULL,
    level           INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 5),
    crop_id         INTEGER REFERENCES crops(id) ON DELETE SET NULL,
    watered_times   INTEGER NOT NULL DEFAULT 0 CHECK (watered_times >= 0),
    planted_at      TIMESTAMP,
    last_watered_at TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL,

    UNIQUE(user_id, index)
);

CREATE INDEX idx_plots_user_id ON plots(user_id);
```

### 3.2 crops 表

```sql
CREATE TABLE crops (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_id         INTEGER NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
    seed_type       VARCHAR(32) NOT NULL,
    plant_time      TIMESTAMP NOT NULL,
    duration        INTEGER NOT NULL,
    watered_times   INTEGER NOT NULL DEFAULT 0 CHECK (watered_times >= 0),
    is_harvested    BOOLEAN NOT NULL DEFAULT 0,
    created_at      TIMESTAMP NOT NULL
);

CREATE INDEX idx_crops_plot_id ON crops(plot_id);
CREATE INDEX idx_crops_seed_type ON crops(seed_type);
```

---

## 4. Plot 模型字段说明

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `int` | PK, 自增 | 主键 |
| `user_id` | `int` | FK → `users.id` ON DELETE CASCADE, NOT NULL, index | 所属用户 |
| `index` | `int` | NOT NULL | 地块编号 (1-based) |
| `level` | `int` | NOT NULL, DEFAULT 1, CHECK (1-5) | 地块等级，预留用于浇水效率 |
| `crop_id` | `int \| None` | FK → `crops.id` ON DELETE SET NULL | 当前活跃作物 ID |
| `watered_times` | `int` | NOT NULL, DEFAULT 0, CHECK >= 0 | 当前作物的累计浇水次数 |
| `planted_at` | `datetime \| None` | nullable | 当前作物种植时间 |
| `last_watered_at` | `datetime \| None` | nullable | 上次浇水时间 |
| `updated_at` | `datetime` | NOT NULL, auto-update | 记录更新时间 |

**唯一约束**: `(user_id, index)` — 同一用户的每个地块编号唯一。

### Plot 方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `has_crop()` | `bool` | 地块是否有当前作物 |

---

## 5. Crop 模型字段说明

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `int` | PK, 自增 | 主键 |
| `plot_id` | `int` | FK → `plots.id` ON DELETE CASCADE, NOT NULL, index | 所属地块 |
| `seed_type` | `str` (32) | NOT NULL | 种子类型（如 `wheat`, `carrot`, `tomato`） |
| `plant_time` | `datetime` | NOT NULL | 种植时间（UTC） |
| `duration` | `int` | NOT NULL | 基础成长时间（秒），种植时从 `SeedConfig.grow_time` 固化 |
| `watered_times` | `int` | NOT NULL, DEFAULT 0, CHECK >= 0 | 累计浇水次数 |
| `is_harvested` | `bool` | NOT NULL, DEFAULT False | 是否已收获 |
| `created_at` | `datetime` | NOT NULL | 创建时间（UTC） |

**成熟判断**：使用 `game_engine.is_mature(crop.plant_time, crop.duration, crop.watered_times, water_bonus)`。

---

## 6. 关系说明

```
User (1) ──< Plot (N)
    │              │
    │              └──< Crop (N)
    │                    每个 Plot 同一时刻最多一个活跃 Crop（通过 crop_id）
    │
    └──< Session (N)
```

- **User → Plot**: 一对多
- **Plot → Crop**: 一对多，一个地块可多次种植（收获后产生新 Crop）
- **Plot.crop_id**: FK 指向当前活跃 Crop（nullable）
- **Cascade**: Crop 随 Plot 删除而删除 (`ON DELETE CASCADE`)
- **Plot.crop_id** 外键使用 `ON DELETE SET NULL`（作物记录被物理删除时，地块不受影响）

---

## 7. 完整 Python 实现代码

```python
"""Farm data models: Plot and Crop."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Plot(Base):
    """玩家的一块耕地。"""
    __tablename__ = "plots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    crop_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("crops.id", ondelete="SET NULL"), nullable=True
    )
    watered_times: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    planted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_watered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    current_crop = relationship("Crop", back_populates="plot", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("user_id", "index", name="uix_user_plot_index"),
        CheckConstraint("level BETWEEN 1 AND 5", name="chk_plot_level"),
        CheckConstraint("watered_times >= 0", name="chk_watered_non_negative"),
    )

    def has_crop(self) -> bool:
        return self.crop_id is not None


class Crop(Base):
    """单次种植的生命周期记录。"""
    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seed_type: Mapped[str] = mapped_column(String(32), nullable=False)
    plant_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    watered_times: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_harvested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
    )

    plot = relationship("Plot", back_populates="current_crop", lazy="select")

    __table_args__ = (
        CheckConstraint("watered_times >= 0", name="chk_crop_watered_non_negative"),
    )
```

---

## 8. 使用示例

### 8.1 查询用户所有地块（含当前作物）

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.farm import Plot

stmt = (
    select(Plot)
    .where(Plot.user_id == user_id)
    .options(selectinload(Plot.current_crop))
    .order_by(Plot.index)
)
result = await db.execute(stmt)
plots = list(result.scalars().all())

for plot in plots:
    if plot.has_crop() and plot.current_crop:
        print(f"地块 {plot.index}: {plot.current_crop.seed_type}")
    else:
        print(f"地块 {plot.index}: 空闲")
```

### 8.2 判断作物成熟

```python
from app.services.game_engine import is_mature, calc_growth_stage
from app.core.constants import SEED_MAP

plot: Plot = ...
crop = plot.current_crop
seed = SEED_MAP.get(crop.seed_type)

mature = is_mature(crop.plant_time, crop.duration, crop.watered_times, seed.water_bonus)
stage = calc_growth_stage(crop.plant_time, crop.duration, crop.watered_times, seed.water_bonus)
```

---

## 9. 扩展预留

| 方向 | 预留设计 |
|------|----------|
| 肥料/道具 | 在 Crop 上增加 `bonus_seconds` 字段 |
| 枯萎机制 | 增加 `withered_at` 字段 |
| 地块等级 | `level` 字段已预留（1-5级） |
| 社交偷菜 | Crop 表含 `seed_type` 和 `plant_time`，可用于计算可偷时机 |
