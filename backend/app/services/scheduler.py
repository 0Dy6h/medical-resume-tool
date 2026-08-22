"""Lightweight in-process subscription scan scheduler.

Runs a daemon thread that wakes once per day at the configured time and
scans all subscriptions.  The clock is injectable so tests never depend
on real wall time.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.services.database import DatabaseEngine
from app.services.repositories import scan_subscriptions


Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


class SubscriptionScheduler:
    """Daily subscription scan scheduler with injectable clock."""

    def __init__(
        self,
        engine: DatabaseEngine,
        *,
        hour: int = 9,
        minute: int = 0,
        enabled: bool = True,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._hour = hour
        self._minute = minute
        self._enabled = enabled
        self._clock: Clock = clock or _default_clock
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
        return scan_subscriptions(self._engine, self._clock())

    def _next_wait_seconds(self) -> float:
        now = self._clock()
        target = now.replace(hour=self._hour, minute=self._minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()

    def _loop(self) -> None:
        while not self._stop.is_set():
            wait = self._next_wait_seconds()
            if self._stop.wait(timeout=wait):
                break
            try:
                scan_subscriptions(self._engine, self._clock())
            except Exception:
                pass
