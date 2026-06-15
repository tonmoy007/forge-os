"""End-to-end failure-path lifecycle flows (P12.03).

The engine must refuse to advance canonical state when a precondition fails, and
must isolate misbehaving execution surfaces (hooks, agents) from the lifecycle.
These flows assert the *negative* guarantees: a failure never silently advances
state, and a slow/failing surface never stalls or corrupts it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import yaml
from typer.testing import CliRunner

from forge_os.cli.main import app
from forge_os.core.state_manager import StateManager
from forge_os.events import read_events
from forge_os.hooks import HookRegistry
from forge_os.project.rework_planner import ReworkPlanner
from forge_os.project.scaffold import initialize_project


def _state() -> dict:
    return json.loads(Path(".forge/state.json").read_text(encoding="utf-8"))


# ── CLI end-to-end failure paths ──────────────────────────────────────────────


def test_gate_block_halts_advance_and_preserves_state(project: Path, cli: CliRunner) -> None:
    # The srs gate requires SRS.md, which does not exist yet.
    advance = cli.invoke(app, ["stage", "advance"])

    assert advance.exit_code == 1
    assert "Required file is missing" in advance.output
    # A failed gate marks the stage "blocked" but never advances the pointer.
    assert _state()["current_stage_id"] == "srs"
    assert _state()["stages"][0]["status"] == "blocked"


def test_agent_contract_failure_does_not_advance_state(project: Path, cli: CliRunner) -> None:
    config_path = project / ".forge" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["dummy"]["create_outputs"] = False
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    run = cli.invoke(app, ["agent", "run"])

    assert run.exit_code == 1
    assert "Required output is missing" in run.output
    assert not (project / "SRS.md").exists()

    record = json.loads((project / ".forge" / "agent-runs.jsonl").read_text(encoding="utf-8"))
    assert record["status"] == "contract_failed"
    assert _state()["current_stage_id"] == "srs"  # a failed run never advances state


def test_stage_override_requires_reason_then_audits(project: Path, cli: CliRunner) -> None:
    # Without --reason the destructive jump is refused and state is preserved.
    no_reason = cli.invoke(app, ["stage", "override", "deploy"])
    assert no_reason.exit_code != 0
    assert _state()["current_stage_id"] == "srs"

    # With --reason it jumps and writes an audited StageOverride event.
    audited = cli.invoke(app, ["stage", "override", "deploy", "--reason", "Emergency release"])
    assert audited.exit_code == 0, audited.output
    assert _state()["current_stage_id"] == "deploy"

    last_event = json.loads(
        Path(".forge/events.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert last_event["event_type"] == "StageOverride"
    assert last_event["payload"]["reason"] == "Emergency release"


# ── Component-integration failure paths (engine + hooks / rework planner) ──────


def test_slow_hook_timeout_does_not_block_advance(tmp_path: Path) -> None:
    # A hook that exceeds its timeout must be isolated: the stage still advances
    # and the lifecycle event is still recorded (ADR-006 optional-layer safety).
    initialize_project(tmp_path, project_name="Demo", profile="minimal")
    _ = (tmp_path / "SRS.md").write_text("# Requirements\n", encoding="utf-8")

    registry = HookRegistry()

    def slow_hook(event: object) -> None:
        time.sleep(0.05)  # exceeds the 1ms timeout below

    registry.register("StageCompleted", slow_hook, name="slow", timeout_seconds=0.001)
    manager = StateManager.for_project(tmp_path, registry)

    state = manager.advance()

    assert state.current_stage_id == "build"
    event_types = [event.event_type for event in read_events(tmp_path / ".forge" / "events.jsonl")]
    assert "StageCompleted" in event_types


def test_backtrack_rework_blocked_until_approved(tmp_path: Path) -> None:
    # Rework is destructive (it marks downstream artifacts stale), so running it
    # without explicit approval must be refused.
    planner = ReworkPlanner(tmp_path)
    ticket_id = planner.create_backtrack_ticket(
        reason="Spec changed after build",
        source_stage_id="build",
        target_stage_id="spec",
    )

    assert planner.run_rework(ticket_id) is False  # not approved -> blocked
    assert planner.approve_ticket(ticket_id) is True
    assert planner.run_rework(ticket_id) is True  # approved -> proceeds
