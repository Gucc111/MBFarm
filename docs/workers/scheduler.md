# Scheduler Worker

## 模块职责

`app/workers/scheduler.py` — 后台定时任务调度器，负责到期处理。

## 设计决策

- 使用 APScheduler（AsyncIOScheduler）与 FastAPI 集成
- 定时扫描到期作物，触发成熟通知
- 定时清理过期肥料（如有 expiration 字段）
- 定时保存/持久化（可预留热备份）

## Python 实现

```python
"""Background scheduler — periodic tasks for the farm game."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.database import AsyncSessionLocal
from app.models.farm import Crop
from app.models.item import Inventory
from app.repositories.farm_repo import FarmRepo
from app.repositories.item_repo import ItemRepo
from app.services.friend_service import FriendService

logger = logging.getLogger(__name__)


class SchedulerWorker:
    """定时任务调度器。"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._started = False

    async def _cleanup(self):
        """清理过期作物（弃种超过一定时间的记录）。"""
        async with AsyncSessionLocal() as db:
            try:
                repo = FarmRepo(db)
                # 此处可扩展：清除种植超过 N 天且未收获的作物
                logger.info("Cron cleanup: done")
            except Exception:
                logger.exception("Cron cleanup failed")

    async def _maturity_check(self):
        """检查并标记已成熟的作物（可选：推送通知）。"""
        async with AsyncSessionLocal() as db:
            try:
                repo = FarmRepo(db)
                crops = await repo.get_mature_crops(user_id=-1)  # all users
                if crops:
                    logger.info(f"Maturity check: {len(crops)} mature crops found")
                    # 后续可扩展 WebSocket 推送给种植者
            except Exception:
                logger.exception("Maturity check failed")

    def start(self):
        """启动调度器。"""
        if self._started:
            return

        # 每 5 分钟检查作物成熟状态
        self.scheduler.add_job(
            self._maturity_check,
            "interval",
            minutes=5,
            id="maturity_check",
            replace_existing=True,
        )

        # 每天凌晨 3 点清理过期记录
        self.scheduler.add_job(
            self._cleanup,
            "cron",
            hour=3,
            minute=0,
            id="cleanup",
            replace_existing=True,
        )

        self.scheduler.start()
        self._started = True
        logger.info("SchedulerWorker started")

    def stop(self):
        """停止调度器。"""
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            logger.info("SchedulerWorker stopped")
```

## 在 main.py 中集成

```python
from app.workers.scheduler import SchedulerWorker

scheduler_worker = SchedulerWorker()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler_worker.start()
    yield
    # Shutdown
    scheduler_worker.stop()


app = FastAPI(title="MB Farm", lifespan=lifespan)
```

## 调度任务列表

| 任务              | 频率        | 说明                     |
|-------------------|-------------|--------------------------|
| maturity_check    | 每 5 分钟   | 扫描已成熟但未收获作物     |
| cleanup           | 每天凌晨 3  | 清理过期/废弃记录          |
