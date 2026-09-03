"""每日维护调度器（A3 自动抓取闭环）。

每天在配置的时钟点执行一次维护循环：
  定时抓取（单飞，可与手动抓取互斥）→ 去重更新 → 订阅扫描 → 健康度记录。

时钟可注入，测试不依赖真实墙时。抓取部分复用 execute_crawl_run，
失败原因与进度落在 crawl_runs / institutions 上，前台可见。
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.services.crawler import (
    execute_crawl_run,
    release_crawl_slot,
    try_acquire_crawl_slot,
)
from app.services.database import DatabaseEngine
from app.services.repositories import (
    create_crawl_run,
    list_crawl_runs,
    list_institutions,
    scan_subscriptions,
)

logger = logging.getLogger("app.scheduler")

Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


class DailyScheduler:
    """每日「抓取 → 订阅扫描」维护循环，时钟与开关均可注入。"""

    def __init__(
        self,
        engine: DatabaseEngine,
        *,
        hour: int = 9,
        minute: int = 0,
        enabled: bool = True,
        clock: Clock | None = None,
        auto_crawl: bool = True,
        crawl_delay: float = 1.0,
        catch_up: bool = True,
    ) -> None:
        self._engine = engine
        self._hour = hour
        self._minute = minute
        self._enabled = enabled
        self._clock: Clock = clock or _default_clock
        self._auto_crawl = auto_crawl
        self._crawl_delay = crawl_delay
        self._catch_up = catch_up
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start(self) -> None:
        if not self._enabled:
            return
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def scan_once(self) -> dict:
        """仅执行订阅扫描（供既有调用与测试使用）。"""
        return scan_subscriptions(self._engine, self._clock())

    def run_cycle_once(self) -> dict[str, Any]:
        """执行一次完整维护循环：自动抓取（可选、单飞）→ 订阅扫描。"""
        crawl_result: dict[str, Any] | None = None
        if self._auto_crawl:
            crawl_result = self._auto_crawl_once()
        scan_result = scan_subscriptions(self._engine, self._clock())
        return {"crawl": crawl_result, "scan": scan_result}

    def _auto_crawl_once(self) -> dict[str, Any] | None:
        """对全部启用机构跑一轮自动抓取；与其他抓取互斥，失败不中断扫描。"""
        if not try_acquire_crawl_slot():
            logger.warning("自动抓取跳过：已有抓取任务执行中（单飞）")
            return None
        try:
            institutions = [item for item in list_institutions(self._engine) if item["enabled"]]
            if not institutions:
                logger.info("自动抓取跳过：没有已启用机构")
                return None
            run_id = create_crawl_run(
                self._engine, [item["id"] for item in institutions], trigger="auto"
            )
            result = execute_crawl_run(
                self._engine, run_id, institutions, self._crawl_delay
            )
            if result["failure_count"]:
                logger.warning(
                    "自动抓取完成但有失败 run_id=%s success=%s failure=%s",
                    run_id,
                    result["success_count"],
                    result["failure_count"],
                )
            return result
        except Exception:
            logger.exception("自动抓取执行异常")
            return None
        finally:
            release_crawl_slot()

    def maybe_catch_up(self) -> dict[str, Any] | None:
        """启动补跑：服务进程错过今日时钟点（晚于 09:00 启动、机器休眠、
        部署重启）时，若最近 24 小时内没有任何 auto 抓取记录，则立即补跑
        一轮维护循环——否则「每日自动抓取」在进程不常驻的机器上形同虚设。

        独立于 enabled（那是线程闸门）；auto_crawl 关闭时无抓取可补，直接跳过。
        """
        if not self._catch_up or not self._auto_crawl:
            return None
        if self._recent_auto_run_exists():
            return None
        logger.info("调度补跑：最近 24 小时内无自动抓取记录，启动即执行一轮维护循环")
        return self.run_cycle_once()

    def _recent_auto_run_exists(self) -> bool:
        cutoff = self._clock() - timedelta(hours=24)
        for run in list_crawl_runs(self._engine, limit=50):
            if run.get("trigger") != "auto":
                continue
            started = run.get("started_at")
            if not started:
                continue
            try:
                started_dt = datetime.fromisoformat(str(started))
            except ValueError:
                continue
            if started_dt.tzinfo is None:
                started_dt = started_dt.replace(tzinfo=timezone.utc)
            if started_dt >= cutoff:
                return True
        return False

    def _next_wait_seconds(self) -> float:
        now = self._clock()
        target = now.replace(hour=self._hour, minute=self._minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()

    def _loop(self) -> None:
        try:
            self.maybe_catch_up()
        except Exception:
            # 补跑失败不影响定时循环本身；异常留痕，不允许静默吞掉。
            logger.exception("调度补跑执行失败")
        while not self._stop.is_set():
            wait = self._next_wait_seconds()
            if self._stop.wait(timeout=wait):
                break
            try:
                self.run_cycle_once()
            except Exception:
                # 每日循环不能因单次异常退出；异常必须留痕，不允许静默吞掉。
                logger.exception("每日维护循环执行失败")
