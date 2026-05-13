"""Tests for ClaudeCodeAdapter (Slice 1) — all subprocess calls mocked."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forge_os.adapters.base import AgentHandle, KernelAdapter
from forge_os.adapters.claude_code import ClaudeCodeAdapter, ClaudeCodeSpawnError
from forge_os.adapters.claude_code.runner import RunResult, StreamEvent, _parse_stream_lines
from forge_os.adapters.claude_code.tool_map import (
    DEFAULT_ABSTRACT_TOOLS,
    to_abstract_tools,
    to_claude_tools,
)
from forge_os.agents.models import AgentDefinition

# ── Fixtures ─────────────────────────────────────────────────────────────────

FIXTURE_STREAM_JSON = "\n".join([
    json.dumps({"type": "text", "content": "Analyzing the codebase..."}),
    json.dumps({"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "SRS.md"}}),
    json.dumps({"type": "tool_result", "tool_use_id": "t1", "content": "# SRS content"}),
    json.dumps({"type": "text", "content": "Done. Produced SRS.md."}),
    json.dumps({"type": "message", "role": "assistant", "content": []}),
])

FIXTURE_STREAM_JSON_ERROR = "\n".join([
    json.dumps({"type": "text", "content": "Trying..."}),
    json.dumps({"type": "error", "error": {"type": "api_error", "message": "rate limited"}}),
])


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def persona() -> AgentDefinition:
    return AgentDefinition(
        id="srs-agent",
        name="SRS Agent",
        category="stage",
        role="Software architect",
        prompt="Write a Software Requirements Specification.",
        stage_ids=["srs"],
        default_tools=["read_file", "write_file"],
    )


@pytest.fixture
def adapter(project_root: Path) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter(project_root, claude_bin="claude", max_turns=5, timeout=30)


def _make_proc(stdout: str = "", stderr: str = "", returncode: int = 0) -> MagicMock:
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


# ── Tool map tests ────────────────────────────────────────────────────────────

class TestToolMap:
    def test_to_claude_tools_maps_known(self) -> None:
        assert to_claude_tools(["read_file", "write_file"]) == ["Read", "Write"]

    def test_to_claude_tools_drops_unknown(self) -> None:
        assert to_claude_tools(["read_file", "nonexistent"]) == ["Read"]

    def test_to_abstract_tools_round_trips(self) -> None:
        abstract = ["read_file", "bash", "list_files"]
        claude = to_claude_tools(abstract)
        assert to_abstract_tools(claude) == abstract

    def test_default_abstract_tools_nonempty(self) -> None:
        assert len(DEFAULT_ABSTRACT_TOOLS) >= 5
        assert "read_file" in DEFAULT_ABSTRACT_TOOLS
        assert "write_file" in DEFAULT_ABSTRACT_TOOLS


# ── Stream-json parser tests ──────────────────────────────────────────────────

class TestStreamParser:
    def test_parses_text_events(self) -> None:
        events = list(_parse_stream_lines(FIXTURE_STREAM_JSON))
        text_events = [e for e in events if e.type == "text"]
        assert len(text_events) == 2
        assert text_events[0].content == "Analyzing the codebase..."

    def test_parses_tool_use_events(self) -> None:
        events = list(_parse_stream_lines(FIXTURE_STREAM_JSON))
        tool_uses = [e for e in events if e.type == "tool_use"]
        assert len(tool_uses) == 1
        assert tool_uses[0].tool_name == "Read"
        assert tool_uses[0].tool_input == {"file_path": "SRS.md"}

    def test_skips_blank_lines(self) -> None:
        raw = "\n".join([
            "",
            json.dumps({"type": "text", "content": "hello"}),
            "   ",
            json.dumps({"type": "text", "content": "world"}),
        ])
        events = list(_parse_stream_lines(raw))
        assert len(events) == 2

    def test_skips_malformed_json(self) -> None:
        raw = "\n".join([
            json.dumps({"type": "text", "content": "ok"}),
            "not json at all",
            json.dumps({"type": "text", "content": "also ok"}),
        ])
        events = list(_parse_stream_lines(raw))
        assert len(events) == 2

    def test_run_result_text_output(self) -> None:
        events = list(_parse_stream_lines(FIXTURE_STREAM_JSON))
        result = RunResult(returncode=0, events=events)
        assert "Analyzing the codebase" in result.text_output
        assert "Done. Produced SRS.md." in result.text_output

    def test_run_result_tool_uses(self) -> None:
        events = list(_parse_stream_lines(FIXTURE_STREAM_JSON))
        result = RunResult(returncode=0, events=events)
        assert len(result.tool_uses) == 1

    def test_run_result_error_events(self) -> None:
        events = list(_parse_stream_lines(FIXTURE_STREAM_JSON_ERROR))
        result = RunResult(returncode=0, events=events)
        assert len(result.errors) == 1
        assert result.errors[0].error_message == "rate limited"

    def test_stream_event_error_message_fallback(self) -> None:
        ev = StreamEvent(type="error", raw={"error": "plain string error"})
        assert ev.error_message == "plain string error"


# ── Adapter instantiation tests ───────────────────────────────────────────────

class TestClaudeCodeAdapterInit:
    def test_satisfies_protocol(self, adapter: ClaudeCodeAdapter) -> None:
        assert isinstance(adapter, KernelAdapter)

    def test_adapter_id(self, adapter: ClaudeCodeAdapter) -> None:
        assert adapter.adapter_id == "claude-code"

    def test_get_default_tools(self, adapter: ClaudeCodeAdapter) -> None:
        tools = adapter.get_default_tools()
        assert isinstance(tools, list)
        assert "read_file" in tools
        assert "write_file" in tools
        assert "bash" in tools
        assert len(tools) >= 5

    def test_supports_stream(self, adapter: ClaudeCodeAdapter) -> None:
        assert adapter.supports("stream") is True

    def test_supports_hook_events(self, adapter: ClaudeCodeAdapter) -> None:
        assert adapter.supports("hook_events") is True

    def test_does_not_support_acp(self, adapter: ClaudeCodeAdapter) -> None:
        assert adapter.supports("acp") is False

    def test_does_not_support_unknown(self, adapter: ClaudeCodeAdapter) -> None:
        assert adapter.supports("nonexistent_capability") is False

    def test_is_acp_available_false(self, adapter: ClaudeCodeAdapter) -> None:
        assert adapter.is_acp_available() is False


# ── spawn_agent tests (mocked subprocess) ────────────────────────────────────

class TestSpawnAgent:
    def test_returns_completed_handle(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            handle = adapter.spawn_agent(persona, "context", ["read_file", "write_file"])

        assert isinstance(handle, AgentHandle)
        assert handle.provider == "claude-code"
        assert handle.status == "completed"
        assert handle.persona_id == "srs-agent"
        assert handle.stage_id == "srs"

    def test_handle_metadata_has_tool_info(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            handle = adapter.spawn_agent(persona, "context", ["read_file", "write_file"])

        assert handle.metadata["adapter"] == "claude-code"
        assert handle.metadata["tool_use_count"] == 1
        assert "read_file" in handle.metadata["tools_granted"]

    def test_handle_outputs_contains_text(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            handle = adapter.spawn_agent(persona, "context", ["read_file"])

        assert len(handle.outputs) == 1
        assert "Analyzing" in handle.outputs[0].description

    def test_filters_unknown_tools(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)) as mock_run:
            adapter.spawn_agent(persona, "context", ["read_file", "nonexistent_tool"])

        cmd = mock_run.call_args[0][0]
        allowed_idx = cmd.index("--allowedTools")
        assert "Read" in cmd[allowed_idx + 1]
        assert "nonexistent_tool" not in cmd[allowed_idx + 1]

    def test_non_zero_exit_raises(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc("", "Internal error", 1)):
            with pytest.raises(ClaudeCodeSpawnError) as exc_info:
                adapter.spawn_agent(persona, "context", ["read_file"])

        assert exc_info.value.returncode == 1
        assert "Internal error" in str(exc_info.value)

    def test_timeout_raises(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 30)):
            with pytest.raises(ClaudeCodeSpawnError) as exc_info:
                adapter.spawn_agent(persona, "context", ["read_file"])

        assert exc_info.value.returncode == -1
        assert "timed out" in str(exc_info.value)

    def test_missing_binary_raises(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError("claude: not found")):
            with pytest.raises(ClaudeCodeSpawnError) as exc_info:
                adapter.spawn_agent(persona, "context", ["read_file"])

        assert "not found" in str(exc_info.value)

    def test_persona_without_stage_ids(
        self, adapter: ClaudeCodeAdapter
    ) -> None:
        persona = AgentDefinition(
            id="generic-agent",
            name="Generic Agent",
            category="cross_stage",
            role="Helper",
            prompt="Do something.",
            stage_ids=[],
        )
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            handle = adapter.spawn_agent(persona, "", ["read_file"])

        assert handle.stage_id is None

    def test_empty_stdout_returns_no_outputs(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc("")):
            handle = adapter.spawn_agent(persona, "context", ["read_file"])

        assert handle.outputs == []

    def test_error_events_cause_spawn_error(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        error_proc = _make_proc(FIXTURE_STREAM_JSON_ERROR, returncode=0)
        with patch("subprocess.run", return_value=error_proc):
            with pytest.raises(ClaudeCodeSpawnError):
                adapter.spawn_agent(persona, "context", ["read_file"])
