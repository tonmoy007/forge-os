from __future__ import annotations

import time
from pathlib import Path

import pytest

from forge_os.core.state_manager import StateManager
from forge_os.events import EventBus, new_event, read_events
from forge_os.hooks import HookRegistry
from forge_os.project.scaffold import initialize_project


def test_event_serialization_round_trip(tmp_path: Path) -> None:
    event_path = tmp_path / "events.jsonl"
    bus = EventBus(event_path)
    event = new_event(
        "StageStarted",
        stage_id="srs",
        actor_type="core",
        actor_id="test",
        payload={"project_id": "demo"},
    )

    results = bus.emit(event)
    events = read_events(event_path)

    assert results == []
    assert len(events) == 1
    assert events[0].event_id == event.event_id
    assert events[0].event_type == "StageStarted"
    assert events[0].stage_id == "srs"
    assert events[0].payload["project_id"] == "demo"


def test_hook_order_is_deterministic(tmp_path: Path) -> None:
    calls: list[str] = []
    registry = HookRegistry()
    registry.register("StageStarted", lambda event: calls.append("second"), name="b", order=20)
    registry.register("StageStarted", lambda event: calls.append("first"), name="a", order=10)
    bus = EventBus(tmp_path / "events.jsonl", registry)

    results = bus.emit(new_event("StageStarted", stage_id="srs"))

    assert calls == ["first", "second"]
    assert [result.status for result in results] == ["succeeded", "succeeded"]


def test_non_blocking_hook_failure_is_isolated(tmp_path: Path) -> None:
    calls: list[str] = []
    registry = HookRegistry()

    def fail_hook(event: object) -> None:
        raise RuntimeError("boom")

    registry.register("StageCompleted", fail_hook, name="failing", order=10)
    registry.register("StageCompleted", lambda event: calls.append("after"), name="after", order=20)
    bus = EventBus(tmp_path / "events.jsonl", registry)

    results = bus.emit(new_event("StageCompleted", stage_id="srs"))

    assert calls == ["after"]
    assert [result.status for result in results] == ["failed", "succeeded"]
    assert read_events(tmp_path / "events.jsonl")[0].event_type == "StageCompleted"


def test_blocking_hook_failure_raises_after_event_append(tmp_path: Path) -> None:
    registry = HookRegistry()

    def fail_hook(event: object) -> None:
        raise RuntimeError("boom")

    registry.register("StageCompleted", fail_hook, name="blocking", blocking=True)
    bus = EventBus(tmp_path / "events.jsonl", registry)

    with pytest.raises(RuntimeError, match="Blocking hook"):
        bus.emit(new_event("StageCompleted", stage_id="srs"))

    assert read_events(tmp_path / "events.jsonl")[0].event_type == "StageCompleted"


def test_hook_timeout_is_reported(tmp_path: Path) -> None:
    registry = HookRegistry()

    def slow_hook(event: object) -> None:
        time.sleep(0.05)

    registry.register("StageStarted", slow_hook, name="slow", timeout_seconds=0.001)
    bus = EventBus(tmp_path / "events.jsonl", registry)

    results = bus.emit(new_event("StageStarted", stage_id="srs"))

    assert results[0].status == "timed_out"


def test_state_manager_stage_commands_emit_normalized_events(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Demo")
    _ = (tmp_path / "SRS.md").write_text("# Requirements\n", encoding="utf-8")
    manager = StateManager.for_project(tmp_path)

    state = manager.advance()

    assert state.current_stage_id == "build"
    event_types = [event.event_type for event in read_events(tmp_path / ".forge" / "events.jsonl")]
    assert event_types == ["GateStarted", "GateCompleted", "StageCompleted", "StageStarted"]


def test_hook_failure_does_not_crash_stage_execution(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Demo")
    _ = (tmp_path / "SRS.md").write_text("# Requirements\n", encoding="utf-8")
    registry = HookRegistry()

    def fail_hook(event: object) -> None:
        raise RuntimeError("boom")

    registry.register("StageCompleted", fail_hook, name="failing")
    manager = StateManager.for_project(tmp_path, registry)

    state = manager.advance()

    assert state.current_stage_id == "build"
    event_types = [event.event_type for event in read_events(tmp_path / ".forge" / "events.jsonl")]
    assert "StageCompleted" in event_types


def test_blocking_hook_can_block_stage_execution(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Demo")
    _ = (tmp_path / "SRS.md").write_text("# Requirements\n", encoding="utf-8")
    registry = HookRegistry()

    def fail_hook(event: object) -> None:
        raise RuntimeError("boom")

    registry.register("StageCompleted", fail_hook, name="blocking", blocking=True)
    manager = StateManager.for_project(tmp_path, registry)

    with pytest.raises(RuntimeError, match="Blocking hook"):
        _ = manager.advance()

    state = manager.load()
    assert state.current_stage_id is None
    assert state.stages[0].status == "complete"
