"""Tests for the hook-timing record + durable sink (FR-HD-005 prerequisite)."""

from __future__ import annotations

from pathlib import Path

from forge_os.hooks.timing import HookTiming, HookTimingLog


def _timing(**overrides: object) -> HookTiming:
    base: dict[str, object] = {
        "event_type": "StageStarted",
        "hook_name": "h",
        "status": "succeeded",
        "duration_ms": 1.5,
    }
    base.update(overrides)
    return HookTiming(**base)


class TestHookTimingLog:
    def test_append_then_read_round_trips(self, tmp_path: Path) -> None:
        log = HookTimingLog(tmp_path)
        log.append(
            [_timing(hook_name="a", duration_ms=2.0), _timing(hook_name="b", duration_ms=3.0)]
        )
        records = log.read_all()
        assert [r.hook_name for r in records] == ["a", "b"]
        assert [r.duration_ms for r in records] == [2.0, 3.0]

    def test_append_is_additive(self, tmp_path: Path) -> None:
        log = HookTimingLog(tmp_path)
        log.append([_timing(hook_name="a")])
        log.append([_timing(hook_name="b")])
        assert [r.hook_name for r in log.read_all()] == ["a", "b"]

    def test_append_empty_is_noop(self, tmp_path: Path) -> None:
        log = HookTimingLog(tmp_path)
        log.append([])
        assert not log.path.exists()  # nothing written, no file created

    def test_read_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert HookTimingLog(tmp_path).read_all() == []

    def test_read_skips_malformed_lines(self, tmp_path: Path) -> None:
        log = HookTimingLog(tmp_path)
        log.append([_timing(hook_name="good")])
        with open(log.path, "a", encoding="utf-8") as handle:
            handle.write("{ not json\n\n")  # corrupt line + a blank line
        assert [r.hook_name for r in log.read_all()] == ["good"]

    def test_recorded_at_is_auto_stamped(self, tmp_path: Path) -> None:
        assert _timing().recorded_at  # ISO timestamp default


def test_hooks_package_imports_without_a_cycle() -> None:
    # Regression guard: importing the hooks package *before* events/core must not
    # hit the latent registry<->events.bus import cycle (broken by deferring the
    # events.model import under TYPE_CHECKING in registry.py). A fresh interpreter
    # is used so the result does not depend on pytest's module collection order.
    import subprocess
    import sys

    subprocess.run(
        [sys.executable, "-c", "import forge_os.hooks.timing; import forge_os.hooks.registry"],
        check=True,
    )
