from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from forge_os.cli.commands.dreamer import dreamer_app
from forge_os.project.scaffold import initialize_project

runner = CliRunner()


def test_digest_command_reports_no_activity_for_quiet_day(tmp_path: Path) -> None:
    _ = initialize_project(tmp_path, project_name="Demo", profile="minimal")

    result = runner.invoke(
        dreamer_app, ["digest", "--path", str(tmp_path), "--date", "1999-01-01"]
    )

    assert result.exit_code == 0, result.output
    assert "No activity" in result.output


def test_scan_command_reports_counts(tmp_path: Path) -> None:
    _ = initialize_project(tmp_path, project_name="Demo", profile="minimal")

    result = runner.invoke(dreamer_app, ["scan", "--path", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Reflections scanned:" in result.output
    assert "Tensions detected:" in result.output


def test_decay_command_reports_summary(tmp_path: Path) -> None:
    _ = initialize_project(tmp_path, project_name="Demo", profile="minimal")

    result = runner.invoke(dreamer_app, ["decay", "--path", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Examined:" in result.output


def test_commands_fail_outside_a_forge_project(tmp_path: Path) -> None:
    result = runner.invoke(dreamer_app, ["decay", "--path", str(tmp_path)])

    assert result.exit_code == 1
