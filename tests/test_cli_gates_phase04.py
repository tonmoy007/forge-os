from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from forge_os.cli.main import app

runner = CliRunner()


def test_gate_list_shows_default_gate() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        result = runner.invoke(app, ["gate", "list"])

        assert result.exit_code == 0, result.output
        assert "srs_exists" in result.output
        assert "required_file" in result.output


def test_gate_check_blocks_missing_required_file() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        result = runner.invoke(app, ["gate", "check", "srs"])

        assert result.exit_code == 1
        assert "Required file is missing" in result.output


def test_gate_check_passes_when_required_file_exists() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        _ = Path("SRS.md").write_text("# Requirements\n", encoding="utf-8")
        result = runner.invoke(app, ["gate", "check", "srs"])

        assert result.exit_code == 0, result.output
        assert "pass" in result.output


def test_gate_report_explains_fix() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        result = runner.invoke(app, ["gate", "report", "--stage", "srs"])

        assert result.exit_code == 0, result.output
        assert "Forge Gate Report" in result.output
        assert "Create `SRS.md`" in result.output


def test_stage_advance_is_blocked_by_missing_required_file() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        result = runner.invoke(app, ["stage", "advance"])

        assert result.exit_code == 1
        assert "Required file is missing" in result.output
