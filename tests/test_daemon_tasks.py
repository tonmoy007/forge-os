"""Tests for forge_os.daemon.tasks (P10.02)."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_os.daemon.state import DaemonStateError, DaemonStateStore
from forge_os.daemon.tasks import HEARTBEAT_INTERVAL_SECONDS, build_scheduled_tasks
from forge_os.schemas.daemon import DaemonState


def seed_state(store: DaemonStateStore) -> None:
    store.save(
        DaemonState(
            daemon_id="daemon-test",
            pid=4321,
            project_root="/tmp/project",
            started_at="2026-06-10T00:00:00Z",
        )
    )


def write_project_config(project_root: Path, observer_value: str) -> None:
    forge = project_root / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "config.yaml").write_text(
        "schema_version: '0.1'\n"
        "project:\n"
        "  name: demo\n"
        "features:\n"
        f"  observer: {observer_value}\n",
        encoding="utf-8",
    )


def write_cost_cap_config(project_root: Path, cost_cap_usd: float) -> None:
    forge = project_root / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "config.yaml").write_text(
        "schema_version: '0.1'\n"
        "project:\n  name: demo\n"
        "features:\n  health_monitor:\n"
        f"    cost_cap_usd: {cost_cap_usd}\n",
        encoding="utf-8",
    )


def test_build_returns_heartbeat_and_dreamer_tasks_by_default(tmp_path: Path) -> None:
    tasks = build_scheduled_tasks(tmp_path, forge_dir=tmp_path / "forge")

    assert [task.name for task in tasks] == [
        "heartbeat", "dreamer-digest", "dreamer-decay", "dreamer-reingest",
    ]
    assert tasks[0].interval_seconds == HEARTBEAT_INTERVAL_SECONDS == 30.0


def test_observer_tasks_absent_when_feature_flag_off(tmp_path: Path) -> None:
    write_project_config(tmp_path, "false")

    tasks = build_scheduled_tasks(tmp_path, forge_dir=tmp_path / "forge")

    assert [task.name for task in tasks] == [
        "heartbeat", "dreamer-digest", "dreamer-decay", "dreamer-reingest",
    ]


def test_observer_tasks_registered_with_default_intervals_when_enabled(tmp_path: Path) -> None:
    write_project_config(tmp_path, "true")

    tasks = build_scheduled_tasks(tmp_path, forge_dir=tmp_path / "forge")

    intervals = {task.name: task.interval_seconds for task in tasks}
    assert intervals == {
        "heartbeat": 30.0,
        "dreamer-digest": 86_400.0,
        "dreamer-decay": 86_400.0,
        "dreamer-reingest": 604_800.0,
        "observer-registry": 60.0,
        "observer-session-cleanup": 300.0,
        "observer-agent-health": 300.0,
        "observer-metrics": 300.0,
    }


def test_observer_tasks_honor_interval_overrides(tmp_path: Path) -> None:
    write_project_config(tmp_path, "{enabled: true, poll_interval_seconds: 15}")

    tasks = build_scheduled_tasks(tmp_path, forge_dir=tmp_path / "forge")

    intervals = {task.name: task.interval_seconds for task in tasks}
    assert intervals["observer-registry"] == 15.0
    assert intervals["observer-metrics"] == 300.0


def test_heartbeat_updates_last_heartbeat_in_store(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge"
    store = DaemonStateStore(forge_dir=forge_dir)
    seed_state(store)
    heartbeat = build_scheduled_tasks(tmp_path, forge_dir=forge_dir)[0]

    result = heartbeat.run()

    reloaded = store.load()
    assert reloaded is not None
    assert reloaded.last_heartbeat is not None
    assert result == {"last_heartbeat": reloaded.last_heartbeat}


def test_heartbeat_raises_daemon_state_error_when_state_missing(tmp_path: Path) -> None:
    heartbeat = build_scheduled_tasks(tmp_path, forge_dir=tmp_path / "forge")[0]

    with pytest.raises(DaemonStateError, match="heartbeat cannot update"):
        _ = heartbeat.run()


def test_dreamer_tasks_registered_with_daily_and_weekly_intervals(tmp_path: Path) -> None:
    # FR-BD-003: the daemon schedules the Dream cycle by default.
    tasks = build_scheduled_tasks(tmp_path, tmp_path)

    intervals = {task.name: task.interval_seconds for task in tasks}
    assert intervals["dreamer-digest"] == 86_400.0
    assert intervals["dreamer-decay"] == 86_400.0
    assert intervals["dreamer-reingest"] == 604_800.0


def test_dreamer_decay_task_runs_against_project_lessons(tmp_path: Path) -> None:
    from forge_os.memory.lessons import LessonStore

    store = LessonStore(tmp_path)
    lesson = store.add("fresh lesson", confidence=0.9)
    _ = store.approve(lesson.id)
    tasks = {task.name: task for task in build_scheduled_tasks(tmp_path, tmp_path)}

    result = tasks["dreamer-decay"].run()

    assert result is not None
    assert result["examined"] == 1


def test_dreamer_digest_task_reports_no_write_for_quiet_project(tmp_path: Path) -> None:
    tasks = {task.name: task for task in build_scheduled_tasks(tmp_path, tmp_path)}

    result = tasks["dreamer-digest"].run()

    assert result == {"written": False, "path": None}


def test_dreamer_task_throttles_when_spend_over_cost_cap(tmp_path: Path) -> None:
    # FR-COST-004 self-throttle: a Dreamer maintenance task built by
    # build_scheduled_tasks skips its work and reports throttled when recorded
    # spend is over the configured cap — proving the gate is wired into the builder.
    from forge_os.events.store import EventStore
    from forge_os.memory.lessons import LessonStore

    forge_dir = tmp_path / "forge"
    seed_state(DaemonStateStore(forge_dir=forge_dir))
    write_cost_cap_config(tmp_path, cost_cap_usd=10.0)
    events = EventStore(tmp_path / ".forge" / "events.db")
    events.append(
        "r1",
        "AdapterSpawnCompleted",
        {"adapter": "claude_code", "metadata": {"total_cost_usd": 50.0}},
    )
    events.close()
    # An approved lesson so an un-throttled decay would return {"examined": 1}.
    lessons = LessonStore(tmp_path)
    approved = lessons.add("fresh lesson", confidence=0.9)
    _ = lessons.approve(approved.id)

    tasks = {task.name: task for task in build_scheduled_tasks(tmp_path, forge_dir=forge_dir)}
    result = tasks["dreamer-decay"].run()

    assert result is not None
    assert result["throttled"] is True
    assert "examined" not in result  # the decay body did NOT run
