"""Tests for forge_os.daemon.scheduler (P10.02). No real sleeps — clock is injected."""

from __future__ import annotations

import threading
from typing import Any

from forge_os.daemon.scheduler import ScheduledTask, TaskRunner


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def make_task(name: str, interval: float, calls: list[str]) -> ScheduledTask:
    def run() -> dict[str, Any]:
        calls.append(name)
        return {"task": name}

    return ScheduledTask(name=name, interval_seconds=interval, run=run)


def test_first_run_pending_runs_all_tasks() -> None:
    calls: list[str] = []
    runner = TaskRunner(
        [make_task("a", 10.0, calls), make_task("b", 60.0, calls)],
        clock=FakeClock(),
    )

    ran = runner.run_pending()

    assert ran == ["a", "b"]
    assert calls == ["a", "b"]


def test_task_not_due_again_before_interval_elapses() -> None:
    calls: list[str] = []
    clock = FakeClock()
    runner = TaskRunner([make_task("a", 10.0, calls)], clock=clock)
    _ = runner.run_pending()

    clock.now = 9.9
    ran = runner.run_pending()

    assert ran == []
    assert calls == ["a"]


def test_task_runs_again_once_interval_elapsed() -> None:
    calls: list[str] = []
    clock = FakeClock()
    runner = TaskRunner([make_task("a", 10.0, calls)], clock=clock)
    _ = runner.run_pending()

    clock.now = 10.0
    ran = runner.run_pending()

    assert ran == ["a"]
    assert calls == ["a", "a"]


def test_run_pending_uses_explicit_now_over_clock() -> None:
    calls: list[str] = []
    clock = FakeClock(now=0.0)
    runner = TaskRunner([make_task("a", 10.0, calls)], clock=clock)
    _ = runner.run_pending(now=0.0)

    ran = runner.run_pending(now=25.0)

    assert ran == ["a"]


def test_tasks_with_different_intervals_track_separate_due_times() -> None:
    calls: list[str] = []
    clock = FakeClock()
    runner = TaskRunner(
        [make_task("fast", 5.0, calls), make_task("slow", 30.0, calls)],
        clock=clock,
    )
    _ = runner.run_pending()

    clock.now = 6.0
    ran = runner.run_pending()

    assert ran == ["fast"]
    assert calls == ["fast", "slow", "fast"]


def test_on_result_receives_task_name_and_result() -> None:
    results: list[tuple[str, dict[str, Any] | None]] = []
    calls: list[str] = []
    runner = TaskRunner(
        [make_task("a", 10.0, calls)],
        clock=FakeClock(),
        on_result=lambda name, result: results.append((name, result)),
    )

    _ = runner.run_pending()

    assert results == [("a", {"task": "a"})]


def test_failing_task_does_not_stop_other_tasks() -> None:
    calls: list[str] = []
    errors: list[tuple[str, Exception]] = []
    results: list[str] = []

    def boom() -> dict[str, Any]:
        raise RuntimeError("boom")

    runner = TaskRunner(
        [
            ScheduledTask(name="boom", interval_seconds=10.0, run=boom),
            make_task("survivor", 10.0, calls),
        ],
        clock=FakeClock(),
        on_result=lambda name, _result: results.append(name),
        on_error=lambda name, exc: errors.append((name, exc)),
    )

    ran = runner.run_pending()

    assert ran == ["boom", "survivor"]
    assert calls == ["survivor"]
    assert results == ["survivor"]
    assert len(errors) == 1
    assert errors[0][0] == "boom"
    assert isinstance(errors[0][1], RuntimeError)


def test_failing_task_is_rescheduled_not_retried_immediately() -> None:
    attempts: list[float] = []
    clock = FakeClock()

    def boom() -> dict[str, Any]:
        attempts.append(clock.now)
        raise RuntimeError("boom")

    runner = TaskRunner(
        [ScheduledTask(name="boom", interval_seconds=10.0, run=boom)],
        clock=clock,
        on_error=lambda _name, _exc: None,
    )
    _ = runner.run_pending()

    clock.now = 5.0
    _ = runner.run_pending()
    clock.now = 10.0
    _ = runner.run_pending()

    assert attempts == [0.0, 10.0]


def test_run_forever_stops_when_event_set_by_sleep() -> None:
    calls: list[str] = []
    stop_event = threading.Event()
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 3:
            stop_event.set()

    runner = TaskRunner(
        [make_task("a", 10.0, calls)],
        clock=FakeClock(),
        sleep=fake_sleep,
    )

    runner.run_forever(stop_event, tick_seconds=0.5)

    assert sleep_calls == [0.5, 0.5, 0.5]
    assert calls == ["a"]


def test_run_forever_returns_immediately_when_event_already_set() -> None:
    calls: list[str] = []
    stop_event = threading.Event()
    stop_event.set()
    runner = TaskRunner([make_task("a", 10.0, calls)], clock=FakeClock())

    runner.run_forever(stop_event)

    assert calls == []
