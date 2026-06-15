"""End-to-end happy-path lifecycle flows (P12.02).

Each test drives the real CLI through a full or partial lifecycle on an
ephemeral project and asserts the on-disk state, events, reflections, and
lessons the documented workflow promises — the cross-phase behavior the unit
suite never exercises end to end.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from forge_os.cli.main import app


def _state() -> dict:
    return json.loads(Path(".forge/state.json").read_text(encoding="utf-8"))


def _event_types() -> list[str]:
    lines = Path(".forge/events.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line)["event_type"] for line in lines]


def test_minimal_profile_completes_full_lifecycle(project: Path, cli: CliRunner) -> None:
    stage_ids = [stage["stage_id"] for stage in _state()["stages"]]
    assert stage_ids == ["srs", "build", "deploy"]

    for index, _stage_id in enumerate(stage_ids):
        run = cli.invoke(app, ["agent", "run"])
        assert run.exit_code == 0, run.output
        if index < len(stage_ids) - 1:
            advance = cli.invoke(app, ["stage", "advance"])
            assert advance.exit_code == 0, advance.output

    final = cli.invoke(app, ["stage", "complete", stage_ids[-1]])
    assert final.exit_code == 0, final.output
    assert [stage["status"] for stage in _state()["stages"]] == ["complete", "complete", "complete"]


def test_agent_run_satisfies_srs_gate_and_records_run(project: Path, cli: CliRunner) -> None:
    # The srs gate (required file SRS.md) blocks until the agent produces it.
    assert cli.invoke(app, ["gate", "check", "srs"]).exit_code == 1

    run = cli.invoke(app, ["agent", "run"])
    assert run.exit_code == 0, run.output
    assert "requirements_analyst" in run.output
    assert (project / "SRS.md").exists()

    record = json.loads((project / ".forge" / "agent-runs.jsonl").read_text(encoding="utf-8"))
    assert record["persona_id"] == "requirements_analyst"
    assert record["status"] == "completed"

    assert cli.invoke(app, ["gate", "check", "srs"]).exit_code == 0


def test_stage_completion_records_reflection_and_pending_lesson(
    project: Path, cli: CliRunner
) -> None:
    assert cli.invoke(app, ["agent", "run"]).exit_code == 0  # writes SRS.md (srs gate)
    complete = cli.invoke(app, ["stage", "complete", "srs"])
    assert complete.exit_code == 0, complete.output

    reflections = list((project / ".forge" / "reflections").glob("*.yaml"))
    assert len(reflections) == 1
    reflection = yaml.safe_load(reflections[0].read_text(encoding="utf-8"))["reflection"]
    assert reflection["event_type"] == "StageCompleted"

    lessons = yaml.safe_load(
        (project / ".forge" / "lessons.yaml").read_text(encoding="utf-8")
    )["lessons"]
    pending = [lesson for lesson in lessons if lesson["status"] == "pending"]
    assert len(pending) == 1
    assert pending[0]["source"] == "reflection"


def test_lifecycle_emits_expected_event_sequence(project: Path, cli: CliRunner) -> None:
    assert cli.invoke(app, ["agent", "run"]).exit_code == 0
    assert cli.invoke(app, ["stage", "advance"]).exit_code == 0  # srs -> build

    types = _event_types()
    expected_events = (
        "SubagentStop",
        "GateStarted",
        "GateCompleted",
        "StageCompleted",
        "StageStarted",
    )
    for expected in expected_events:
        assert expected in types, types
    # the srs stage completes before the next stage starts
    assert types.index("StageCompleted") < types.index("StageStarted")

    tail = cli.invoke(app, ["events", "tail", "-n", "5"])
    assert tail.exit_code == 0, tail.output


@pytest.mark.parametrize("project", ["standard"], indirect=True)
def test_standard_profile_walks_first_stages(project: Path, cli: CliRunner) -> None:
    stage_ids = [stage["stage_id"] for stage in _state()["stages"]]
    assert len(stage_ids) == 12
    assert stage_ids[0] == "srs"

    for _stage_id in stage_ids[:3]:
        assert cli.invoke(app, ["agent", "run"]).exit_code == 0
        assert cli.invoke(app, ["stage", "advance"]).exit_code == 0

    assert _state()["current_stage_id"] == stage_ids[3]
