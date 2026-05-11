from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from forge_os.cli.main import app

runner = CliRunner()


def _state() -> dict[str, object]:
    return json.loads(Path(".forge/state.json").read_text(encoding="utf-8"))


def test_stage_list_shows_initialized_stages() -> None:
    with runner.isolated_filesystem():
        init_result = runner.invoke(app, ["init", "--name", "Demo"])
        list_result = runner.invoke(app, ["stage", "list"])

        assert init_result.exit_code == 0, init_result.output
        assert list_result.exit_code == 0, list_result.output
        assert "srs" in list_result.output
        assert "build" in list_result.output
        assert "deploy" in list_result.output


def test_stage_advance_updates_state() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        _ = Path("SRS.md").write_text("# Requirements\n", encoding="utf-8")
        result = runner.invoke(app, ["stage", "advance"])

        assert result.exit_code == 0, result.output
        assert "build" in result.output
        assert _state()["current_stage_id"] == "build"


def test_stage_start_blocks_invalid_transition() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        result = runner.invoke(app, ["stage", "start", "deploy"])

        assert result.exit_code == 1
        assert "Another stage is already active" in result.output
        assert _state()["current_stage_id"] == "srs"


def test_stage_complete_then_start_next_stage() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        _ = Path("SRS.md").write_text("# Requirements\n", encoding="utf-8")
        complete_result = runner.invoke(app, ["stage", "complete", "srs"])
        start_result = runner.invoke(app, ["stage", "start", "build"])

        assert complete_result.exit_code == 0, complete_result.output
        assert start_result.exit_code == 0, start_result.output
        assert _state()["current_stage_id"] == "build"


def test_stage_override_requires_reason_option() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        result = runner.invoke(app, ["stage", "override", "deploy"])

        assert result.exit_code != 0
        assert _state()["current_stage_id"] == "srs"


def test_stage_override_audits_reason() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        result = runner.invoke(
            app,
            ["stage", "override", "deploy", "--reason", "Emergency release"],
        )

        assert result.exit_code == 0, result.output
        assert _state()["current_stage_id"] == "deploy"
        lines = Path(".forge/events.jsonl").read_text(encoding="utf-8").splitlines()
        event = json.loads(lines[-1])
        assert event["event_type"] == "StageOverride"
        assert event["payload"]["reason"] == "Emergency release"
