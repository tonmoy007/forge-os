"""Tests for forge_os.daemon.state (P10.01)."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_os.daemon.state import MAX_ALERTS, DaemonStateError, DaemonStateStore
from forge_os.schemas.daemon import DaemonAlert, DaemonState


def make_state(pid: int = 1234) -> DaemonState:
    return DaemonState(
        daemon_id="daemon-test",
        pid=pid,
        project_root="/tmp/project",
        started_at="2026-06-10T00:00:00Z",
    )


def make_alert(alert_id: str) -> DaemonAlert:
    return DaemonAlert(
        alert_id=alert_id,
        created_at="2026-06-10T00:00:00Z",
        source="test",
        severity="info",
        message="something happened",
    )


def test_save_then_load_round_trips_state(tmp_path: Path) -> None:
    store = DaemonStateStore(forge_dir=tmp_path)
    saved = make_state()

    store.save(saved)
    loaded = store.load()

    assert loaded is not None
    assert loaded.model_dump() == saved.model_dump()


def test_load_returns_none_when_state_file_missing(tmp_path: Path) -> None:
    store = DaemonStateStore(forge_dir=tmp_path)

    assert store.load() is None


def test_load_raises_daemon_state_error_on_corrupt_json(tmp_path: Path) -> None:
    store = DaemonStateStore(forge_dir=tmp_path)
    store.daemon_dir.mkdir(parents=True)
    _ = store.state_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(DaemonStateError, match="Corrupt daemon state file"):
        _ = store.load()


def test_load_raises_daemon_state_error_on_schema_violation(tmp_path: Path) -> None:
    store = DaemonStateStore(forge_dir=tmp_path)
    store.daemon_dir.mkdir(parents=True)
    _ = store.state_path.write_text('{"daemon_id": "x"}', encoding="utf-8")

    with pytest.raises(DaemonStateError, match="Corrupt daemon state file"):
        _ = store.load()


def test_save_leaves_no_temp_files_behind(tmp_path: Path) -> None:
    store = DaemonStateStore(forge_dir=tmp_path)

    store.save(make_state())

    assert [path.name for path in store.daemon_dir.iterdir()] == ["state.json"]


def test_clear_removes_state_file(tmp_path: Path) -> None:
    store = DaemonStateStore(forge_dir=tmp_path)
    store.save(make_state())

    store.clear()

    assert store.load() is None


def test_clear_is_a_no_op_when_state_file_missing(tmp_path: Path) -> None:
    store = DaemonStateStore(forge_dir=tmp_path)

    store.clear()

    assert store.load() is None


def test_add_alert_appends_and_persists(tmp_path: Path) -> None:
    store = DaemonStateStore(forge_dir=tmp_path)
    store.save(make_state())

    updated = store.add_alert(make_alert("alert-1"))

    assert [alert.alert_id for alert in updated.alerts] == ["alert-1"]
    reloaded = store.load()
    assert reloaded is not None
    assert [alert.alert_id for alert in reloaded.alerts] == ["alert-1"]


def test_add_alert_caps_list_at_most_recent_100(tmp_path: Path) -> None:
    store = DaemonStateStore(forge_dir=tmp_path)
    store.save(make_state())

    for index in range(MAX_ALERTS + 5):
        _ = store.add_alert(make_alert(f"alert-{index}"))

    reloaded = store.load()
    assert reloaded is not None
    assert len(reloaded.alerts) == MAX_ALERTS
    assert reloaded.alerts[0].alert_id == "alert-5"
    assert reloaded.alerts[-1].alert_id == f"alert-{MAX_ALERTS + 4}"


def test_add_alert_raises_when_no_state_exists(tmp_path: Path) -> None:
    store = DaemonStateStore(forge_dir=tmp_path)

    with pytest.raises(DaemonStateError, match="No daemon state"):
        _ = store.add_alert(make_alert("alert-1"))


def test_record_task_run_tracks_ok_runs(tmp_path: Path) -> None:
    store = DaemonStateStore(forge_dir=tmp_path)
    store.save(make_state())

    store.record_task_run("heartbeat", status="ok")
    store.record_task_run("heartbeat", status="ok")

    reloaded = store.load()
    assert reloaded is not None
    task = reloaded.tasks["heartbeat"]
    assert task.runs == 2
    assert task.failures == 0
    assert task.last_status == "ok"
    assert task.last_run_at is not None
    assert task.last_error is None


def test_record_task_run_tracks_failures_with_error_message(tmp_path: Path) -> None:
    store = DaemonStateStore(forge_dir=tmp_path)
    store.save(make_state())

    store.record_task_run("dreamer", status="error", error="boom")

    reloaded = store.load()
    assert reloaded is not None
    task = reloaded.tasks["dreamer"]
    assert task.runs == 1
    assert task.failures == 1
    assert task.last_status == "error"
    assert task.last_error == "boom"


def test_record_task_run_raises_when_no_state_exists(tmp_path: Path) -> None:
    store = DaemonStateStore(forge_dir=tmp_path)

    with pytest.raises(DaemonStateError, match="No daemon state"):
        store.record_task_run("heartbeat", status="ok")


def test_add_alert_warns_when_cap_drops_oldest(tmp_path, caplog) -> None:
    import logging

    from forge_os.daemon.state import MAX_ALERTS
    from forge_os.schemas.daemon import DaemonAlert, DaemonState

    store = DaemonStateStore(tmp_path)
    state = DaemonState(daemon_id="d", pid=1, project_root=".", started_at="2026-01-01T00:00:00Z")
    state.alerts = [
        DaemonAlert(
            alert_id=f"a{i}", created_at="2026-01-01T00:00:00Z",
            source="test", severity="info", message="m",
        )
        for i in range(MAX_ALERTS)
    ]
    store.save(state)
    overflow = DaemonAlert(
        alert_id="new", created_at="2026-01-01T00:00:00Z",
        source="test", severity="info", message="m",
    )

    # Runner tests set propagate=False on the parent "forge.daemon" logger;
    # restore propagation here so caplog's root handler sees the warning.
    daemon_logger = logging.getLogger("forge.daemon")
    previous_propagate = daemon_logger.propagate
    daemon_logger.propagate = True
    try:
        with caplog.at_level(logging.WARNING, logger="forge.daemon.state"):
            updated = store.add_alert(overflow)
    finally:
        daemon_logger.propagate = previous_propagate

    assert len(updated.alerts) == MAX_ALERTS
    assert updated.alerts[-1].alert_id == "new"
    assert updated.alerts[0].alert_id == "a1"  # oldest dropped
    assert any("alert cap reached" in record.message for record in caplog.records)
