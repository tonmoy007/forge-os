from __future__ import annotations

import json
from pathlib import Path

import yaml

from forge_os.core.state_manager import StateManager, StateTransitionError
from forge_os.events import read_events
from forge_os.gates import GateCoordinator
from forge_os.project.scaffold import initialize_project


def _write_gates(root: Path, gates: list[dict[str, object]]) -> None:
    _ = (root / "pipeline" / "gates.yaml").write_text(
        yaml.safe_dump({"schema_version": "0.1", "gates": gates}, sort_keys=False),
        encoding="utf-8",
    )


def test_required_file_gate_passes_when_file_exists(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Demo")
    _ = (tmp_path / "SRS.md").write_text("# Requirements\n", encoding="utf-8")
    coordinator = GateCoordinator(tmp_path)

    results = coordinator.evaluate_stage("srs")

    assert len(results) == 1
    assert results[0].status == "pass"
    assert results[0].blocking is False


def test_required_file_gate_blocks_when_missing(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Demo")
    coordinator = GateCoordinator(tmp_path)

    results = coordinator.evaluate_stage("srs")

    assert results[0].status == "fail"
    assert results[0].blocking is True
    assert "Create `SRS.md`" in (results[0].fix_hint or "")


def test_pattern_gate_passes_and_fails_deterministically(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Demo")
    _ = (tmp_path / "SRS.md").write_text("# Requirements\nMUST ship locally.\n", encoding="utf-8")
    _write_gates(
        tmp_path,
        [
            {
                "id": "srs_must",
                "name": "SRS contains MUST",
                "type": "pattern",
                "stage_id": "srs",
                "severity": "blocking",
                "criteria": {"path": "SRS.md", "pattern": "MUST"},
                "enabled": True,
            }
        ],
    )
    coordinator = GateCoordinator(tmp_path)

    first = coordinator.evaluate_stage("srs")
    second = coordinator.evaluate_stage("srs")

    assert first[0].status == "pass"
    assert second[0].status == "pass"
    assert first[0].summary == second[0].summary


def test_pattern_gate_failure_has_clear_fix_hint(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Demo")
    _ = (tmp_path / "SRS.md").write_text("# Requirements\n", encoding="utf-8")
    _write_gates(
        tmp_path,
        [
            {
                "id": "srs_must",
                "name": "SRS contains MUST",
                "type": "pattern",
                "stage_id": "srs",
                "severity": "blocking",
                "criteria": {"path": "SRS.md", "pattern": "MUST"},
                "enabled": True,
            }
        ],
    )
    coordinator = GateCoordinator(tmp_path)

    results = coordinator.evaluate_stage("srs")

    assert results[0].status == "fail"
    assert results[0].blocking is True
    assert "Update `SRS.md`" in (results[0].fix_hint or "")


def test_warning_and_advisory_failures_do_not_block(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Demo")
    _write_gates(
        tmp_path,
        [
            {
                "id": "warning_missing",
                "name": "Optional warning file",
                "type": "required_file",
                "stage_id": "srs",
                "severity": "warning",
                "criteria": {"path": "optional-warning.md"},
                "enabled": True,
            },
            {
                "id": "advisory_missing",
                "name": "Optional advisory file",
                "type": "required_file",
                "stage_id": "srs",
                "severity": "advisory",
                "criteria": {"path": "optional-advisory.md"},
                "enabled": True,
            },
        ],
    )
    coordinator = GateCoordinator(tmp_path)

    results = coordinator.evaluate_stage("srs")

    assert [result.status for result in results] == ["skipped", "warn"]
    assert not coordinator.has_blocking_failures(results)


def test_stage_advance_is_gate_protected_and_persists_results(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Demo")
    manager = StateManager.for_project(tmp_path)

    try:
        manager.advance()
    except StateTransitionError as exc:
        assert "Required file is missing" in str(exc)
    else:
        raise AssertionError("Expected missing SRS gate to block advancement")

    state = json.loads((tmp_path / ".forge" / "state.json").read_text(encoding="utf-8"))
    assert state["gates"]["srs"]["blocked"] is True
    assert state["stages"][0]["status"] == "blocked"


def test_gate_events_are_emitted(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Demo")
    _ = (tmp_path / "SRS.md").write_text("# Requirements\n", encoding="utf-8")
    manager = StateManager.for_project(tmp_path)

    _ = manager.advance()

    event_types = [event.event_type for event in read_events(tmp_path / ".forge" / "events.jsonl")]
    assert "GateStarted" in event_types
    assert "GateCompleted" in event_types
