from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from forge_os.core.state_manager import StateManager, StateTransitionError, validate_state_file
from forge_os.project.scaffold import initialize_project


def _init_project(root: Path, profile: str = "minimal") -> StateManager:
    initialize_project(root, project_name="Demo", profile=profile)
    return StateManager.for_project(root)


def _state_json(root: Path) -> dict[str, object]:
    return json.loads((root / ".forge" / "state.json").read_text(encoding="utf-8"))


def _event_types(root: Path) -> list[str]:
    events = []
    for line in (root / ".forge" / "events.jsonl").read_text(encoding="utf-8").splitlines():
        events.append(json.loads(line)["event_type"])
    return events


def test_minimal_profile_advances_srs_build_deploy(tmp_path: Path) -> None:
    manager = _init_project(tmp_path)
    _ = (tmp_path / "SRS.md").write_text("# Requirements\n", encoding="utf-8")

    state = manager.advance()
    assert state.current_stage_id == "build"
    assert [stage.status for stage in state.stages] == ["complete", "active", "not_started"]

    state = manager.advance()
    assert state.current_stage_id == "deploy"
    assert [stage.status for stage in state.stages] == ["complete", "complete", "active"]

    state = manager.advance()
    assert state.current_stage_id is None
    assert [stage.status for stage in state.stages] == ["complete", "complete", "complete"]

    state_file = _state_json(tmp_path)
    assert state_file["current_stage_id"] is None
    assert "StageCompleted" in _event_types(tmp_path)


def test_invalid_start_is_blocked_until_previous_stage_complete(tmp_path: Path) -> None:
    manager = _init_project(tmp_path)

    with pytest.raises(StateTransitionError, match="Another stage is already active"):
        _ = manager.start_stage("deploy")

    state = _state_json(tmp_path)
    assert state["current_stage_id"] == "srs"


def test_complete_requires_active_stage(tmp_path: Path) -> None:
    manager = _init_project(tmp_path)

    with pytest.raises(StateTransitionError, match="must be active"):
        _ = manager.complete_stage("build")

    state = _state_json(tmp_path)
    assert state["current_stage_id"] == "srs"


def test_unknown_stage_is_rejected(tmp_path: Path) -> None:
    manager = _init_project(tmp_path)

    with pytest.raises(StateTransitionError, match="Unknown stage"):
        _ = manager.start_stage("missing")


def test_override_requires_reason(tmp_path: Path) -> None:
    manager = _init_project(tmp_path)

    with pytest.raises(StateTransitionError, match="requires"):
        _ = manager.override_stage("deploy", reason="")


def test_override_sets_active_stage_and_logs_reason(tmp_path: Path) -> None:
    manager = _init_project(tmp_path)

    state = manager.override_stage("deploy", reason="Emergency release")

    assert state.current_stage_id == "deploy"
    assert _state_json(tmp_path)["current_stage_id"] == "deploy"

    events = [
        json.loads(line)
        for line in (tmp_path / ".forge" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert events[-1]["event_type"] == "StageOverride"
    assert events[-1]["payload"]["reason"] == "Emergency release"


def test_gate_failure_blocks_completion(tmp_path: Path) -> None:
    manager = _init_project(tmp_path)

    with pytest.raises(StateTransitionError, match="Required file is missing"):
        _ = manager.complete_stage("srs")

    state_file = _state_json(tmp_path)
    stages = state_file["stages"]
    assert isinstance(stages, list)
    assert isinstance(stages[0], dict)
    assert stages[0]["status"] == "blocked"


def test_state_markdown_syncs_after_transition(tmp_path: Path) -> None:
    manager = _init_project(tmp_path)
    _ = (tmp_path / "SRS.md").write_text("# Requirements\n", encoding="utf-8")

    _ = manager.advance()

    mirror = (tmp_path / "pipeline" / "state.md").read_text(encoding="utf-8")
    assert "- Current stage: build" in mirror
    assert "- srs: complete" in mirror
    assert "- build: active" in mirror


def test_atomic_write_failure_preserves_existing_state_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _init_project(tmp_path)
    original = (tmp_path / ".forge" / "state.json").read_text(encoding="utf-8")
    state = manager.load()
    state.metadata["test"] = "changed"

    def fail_replace(source: object, destination: object) -> None:
        _ = source
        _ = destination
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(RuntimeError, match="Failed to atomically write"):
        manager.save(state)

    assert (tmp_path / ".forge" / "state.json").read_text(encoding="utf-8") == original
    assert not list((tmp_path / ".forge").glob(".state.json.tmp-*"))


def test_validate_state_file_accepts_persisted_state(tmp_path: Path) -> None:
    _ = _init_project(tmp_path)

    state = validate_state_file(tmp_path / ".forge" / "state.json")

    assert state.current_stage_id == "srs"
