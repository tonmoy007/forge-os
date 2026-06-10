"""Deterministic interval scheduler for daemon tasks (P10.02)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ScheduledTask:
    """A named callable run every `interval_seconds`."""

    name: str
    interval_seconds: float
    run: Callable[[], dict[str, Any] | None]


class TaskRunner:
    """Run scheduled tasks on injected clock/sleep with per-task failure isolation."""

    def __init__(
        self,
        tasks: list[ScheduledTask],
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        on_result: Callable[[str, dict[str, Any] | None], None] | None = None,
        on_error: Callable[[str, Exception], None] | None = None,
    ) -> None:
        self._tasks = list(tasks)
        self._clock = clock
        self._sleep = sleep
        self._on_result = on_result
        self._on_error = on_error
        self._next_due: dict[str, float] = {}

    def run_pending(self, now: float | None = None) -> list[str]:
        """Run every due task and return the names that ran.

        Tasks with no recorded run are due immediately, so the first call runs all.
        A failing task is reported via `on_error` and never stops the other tasks.
        """

        current = self._clock() if now is None else now
        ran: list[str] = []
        for task in self._tasks:
            due_at = self._next_due.get(task.name)
            if due_at is not None and current < due_at:
                continue
            self._next_due[task.name] = current + task.interval_seconds
            ran.append(task.name)
            try:
                result = task.run()
            except Exception as exc:  # failure isolation: one task must not kill the loop
                if self._on_error is not None:
                    self._on_error(task.name, exc)
                continue
            if self._on_result is not None:
                self._on_result(task.name, result)
        return ran

    def run_forever(self, stop_event: threading.Event, *, tick_seconds: float = 1.0) -> None:
        """Run pending tasks every `tick_seconds` until `stop_event` is set."""

        while not stop_event.is_set():
            _ = self.run_pending()
            if stop_event.is_set():
                break
            self._sleep(tick_seconds)
