"""Tests for the ChannelUseCases bridge layer (FR-CH-001/002/003)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from forge_os.channels.console import ConsoleChannelAdapter
from forge_os.cli.main import app
from forge_os.use_cases.channels import ChannelUseCases

runner = CliRunner()


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--name", "Demo", "--profile", "minimal"])
    assert result.exit_code == 0, result.output
    return tmp_path


def test_submit_message_returns_user_prompt_submit(tmp_path):
    result = ChannelUseCases(tmp_path).submit_message("hello", "alice")
    assert result["event_type"] == "UserPromptSubmit"
    assert result["payload"]["trust_level"] == "untrusted"


def test_broadcast_uses_injected_channel(tmp_path):
    sent: list[str] = []
    use_cases = ChannelUseCases(tmp_path, channel=ConsoleChannelAdapter(sink=sent.append))
    result = use_cases.broadcast_release("v1.0 released")
    assert result["success"] is True
    assert result["channel"] == "console"
    assert sent == ["v1.0 released"]


def test_status_summary_reads_project(project):
    summary = ChannelUseCases(project).status_summary()
    assert "project_id" in summary
    assert "next_action" in summary
    assert "stale_artifacts" in summary


def test_status_summary_is_read_only(project):
    # FR-CH-002: status queries must not mutate project state. Pin the invariant
    # by snapshotting state.json + events.jsonl byte-for-byte around the call.
    forge = project / ".forge"
    state = forge / "state.json"
    events = forge / "events.jsonl"
    before = (state.read_bytes(), events.read_bytes() if events.exists() else b"")
    ChannelUseCases(project).status_summary()
    after = (state.read_bytes(), events.read_bytes() if events.exists() else b"")
    assert before == after
