"""Shared fixtures for end-to-end integration tests.

Integration tests drive the real Typer CLI (``forge_os.cli.main:app``) through
full lifecycle flows against an ephemeral project, offline via the DummyAdapter.
No network and no real AI provider — every flow is deterministic (L001/L006).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge_os.cli.main import app

runner = CliRunner()


@pytest.fixture
def cli() -> CliRunner:
    """The Typer CLI runner used to drive lifecycle flows."""
    return runner


@pytest.fixture
def project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Path:
    """A freshly ``forge init``-ed project, with cwd set to it for the test.

    Defaults to the fast 3-stage ``minimal`` profile. Override per-test with an
    indirect parameter::

        @pytest.mark.parametrize("project", ["standard"], indirect=True)
    """
    monkeypatch.chdir(tmp_path)
    profile = getattr(request, "param", "minimal")
    result = runner.invoke(app, ["init", "--name", "Demo", "--profile", profile])
    assert result.exit_code == 0, result.output
    return tmp_path
