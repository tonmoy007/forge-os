"""Tests for the daemon CLI sub-app (P10.04)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge_os.cli.commands.daemon import daemon_app

runner = CliRunner()


@pytest.fixture
def forge_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A minimal on-disk Forge project, with HOME redirected into tmp_path."""

    project = tmp_path / "project"
    (project / ".forge").mkdir(parents=True)
    _ = (project / ".forge" / "config.yaml").write_text("profile: default\n", encoding="utf-8")
    _ = (project / ".forge" / "state.json").write_text("{}\n", encoding="utf-8")
    # DaemonUseCases defaults forge_dir to Path.home() / ".forge" (L001/L005).
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return project


def test_status_reports_not_running_when_no_daemon(forge_project: Path) -> None:
    result = runner.invoke(daemon_app, ["status", "--path", str(forge_project)])

    assert result.exit_code == 0
    assert "Forge Daemon Status" in result.output
    assert "Running" in result.output


def test_stop_reports_no_running_daemon(forge_project: Path) -> None:
    result = runner.invoke(daemon_app, ["stop", "--path", str(forge_project)])

    assert result.exit_code == 0
    assert "No running daemon" in result.output


def test_logs_reports_no_entries_when_log_missing(forge_project: Path) -> None:
    result = runner.invoke(daemon_app, ["logs", "--path", str(forge_project)])

    assert result.exit_code == 0
    assert "No daemon log entries" in result.output


def test_commands_exit_1_outside_a_forge_project(tmp_path: Path) -> None:
    result = runner.invoke(daemon_app, ["status", "--path", str(tmp_path)])

    assert result.exit_code == 1
    assert "No Forge project found" in result.output
