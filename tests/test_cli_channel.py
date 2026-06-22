"""CLI tests for `forge channel` (FR-CH-002/003), driving the real Typer app."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from forge_os.cli.main import app

runner = CliRunner()


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--name", "Demo", "--profile", "minimal"])
    assert result.exit_code == 0, result.output
    return tmp_path


def test_channel_status(project):
    result = runner.invoke(app, ["channel", "status"])
    assert result.exit_code == 0, result.output
    assert "Stage" in result.output
    assert "Next" in result.output


def test_channel_broadcast(project):
    result = runner.invoke(app, ["channel", "broadcast", "Release 1.0 is out"])
    assert result.exit_code == 0, result.output
    assert "Broadcast sent" in result.output
