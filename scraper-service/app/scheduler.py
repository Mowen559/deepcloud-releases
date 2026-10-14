"""
本地轻量异步任务调度器 (LocalScheduler)

零外部 Redis 依赖，直接基于 asyncio 事件循环定时检查 local_spider_job 中
已启用 (status=1) 且配置了 cron_expression 的任务，驱动定时自动抓取。
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .database import get_connection

log = logging.getLogger("scraper.scheduler")


def _match_cron_field(field_val: int, cron_expr: str) -> bool:
    """简易标准 Cron 字段匹配 (*, 步长 */n, 单值 n, 列表 n,m, 范围 a-b)"""
    if cron_expr == "*":
        return True
    if cron_expr.startswith("*/"):
        try:
            step = int(cron_expr[2:])
            return field_val % step == 0
        except ValueError:
            return False
    if "," in cron_expr:
        parts = cron_expr.split(",")
        return any(_match_cron_field(field_val, p.strip()) for p in parts)
    if "-" in cron_expr:
        try:
            start, end = map(int, cron_expr.split("-"))
            return start <= field_val <= end
        except ValueError:
            return False
    try:
        return field_val == int(cron_expr)
    except ValueError:
        return False


def is_cron_due(cron_expr: str, now: datetime) -> bool:
    """
    检查指定时间是否命中 Cron 表达式。
    支持标准 5 段 (分 时 日 月 周) 或 6 段 (秒 分 时 日 月 周) 表达式。
    """
    if not cron_expr:
        return False
    parts = cron_expr.strip().split()
    if len(parts) == 5:
        # 分 时 日 月 周
        minute, hour, dom, month, dow = parts
        sec_match = (now.second == 0)
    elif len(parts) == 6:
        # 秒 分 时 日 月 周
        sec, minute, hour, dom, month, dow = parts
        sec_match = _match_cron_field(now.second, sec)
    else:
        return False

    return (
        sec_match
        and _match_cron_field(now.minute, minute)
        and _match_cron_field(now.hour, hour)
        and _match_cron_field(now.day, dom)
        and _match_cron_field(now.month, month)
        and _match_cron_field((now.weekday() + 1) % 7, dow)  # 0=Sunday
    )


class LocalScheduler:
    def __init__(self, job_service: Any, check_interval_seconds: int = 15):
        self.job_service = job_service
        self.check_interval = check_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_triggered: Dict[int, str] = {}  # 防止同一分钟内重复触发

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("[scheduler] 本地异步定时调度器已启动")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("[scheduler] 本地定时调度器已停止")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("[scheduler] 调度轮询异常: %s", e)
            await asyncio.sleep(self.check_interval)

    async def _tick(self) -> None:
        now = datetime.now()
        current_minute_key = now.strftime("%Y-%m-%d %H:%M")

        with get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("""
                SELECT id, job_name, cron_expression, phase
                FROM local_spider_job
                WHERE status = 1 AND cron_expression IS NOT NULL AND cron_expression != ''
            """).fetchall()

            for r in rows:
                job_id = r["id"]
                cron_expr = r["cron_expression"]
                phase = r["phase"]

                # 若已经在运行中，跳过本次调度
                if phase == "RUNNING":
                    continue

                # 检查该分钟内是否已经触发过
                if self._last_triggered.get(job_id) == current_minute_key:
                    continue

                if is_cron_due(cron_expr, now):
                    self._last_triggered[job_id] = current_minute_key
                    log.info("[scheduler] 定时触发任务: id=%s name=%s cron=%s", job_id, r["job_name"], cron_expr)
                    # 异步执行任务
                    asyncio.create_task(self.job_service.run_job(job_id, trigger_type="SCHEDULE"))
