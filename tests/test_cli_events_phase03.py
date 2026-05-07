from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from forge_os.cli.main import app

runner = CliRunner()


def test_events_list_shows_stage_events() -> None:
    with runner.isolated_filesystem():
        init_result = runner.invoke(app, ["init", "--name", "Demo"])
        _ = Path("SRS.md").write_text("# Requirements\n", encoding="utf-8")
        advance_result = runner.invoke(app, ["stage", "advance"])
        events_result = runner.invoke(app, ["events", "list"])

        assert init_result.exit_code == 0, init_result.output
        assert advance_result.exit_code == 0, advance_result.output
        assert events_result.exit_code == 0, events_result.output
        assert "StageCompleted" in events_result.output
        assert "StageStarted" in events_result.output


def test_events_tail_limits_output() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        _ = Path("SRS.md").write_text("# Requirements\n", encoding="utf-8")
        runner.invoke(app, ["stage", "advance"])
        result = runner.invoke(app, ["events", "tail", "--count", "1"])

        assert result.exit_code == 0, result.output
        assert "StageStarted" in result.output
        assert "StageCompleted" not in result.output


def test_events_list_filters_by_type() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        _ = Path("SRS.md").write_text("# Requirements\n", encoding="utf-8")
        runner.invoke(app, ["stage", "advance"])
        result = runner.invoke(app, ["events", "list", "--type", "StageCompleted"])

        assert result.exit_code == 0, result.output
        assert "StageCompleted" in result.output
        assert "StageStarted" not in result.output
