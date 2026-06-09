"""Tests for ClaudeCodeAdapter (Slice 1) — all subprocess calls mocked."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forge_os.adapters.base import AgentHandle, KernelAdapter
from forge_os.adapters.claude_code import (
    ClaudeCodeAdapter,
    ClaudeCodeSpawnError,
    ClaudeSettingsError,
)
from forge_os.adapters.claude_code.adapter import (
    EVENT_SPAWN_COMPLETED,
    EVENT_SPAWN_FAILED,
    EVENT_SPAWN_STARTED,
    EVENT_STREAM,
)
from forge_os.adapters.claude_code.runner import (
    RunResult,
    StreamEvent,
    _parse_stream_lines,
    run_claude,
)
from forge_os.adapters.claude_code.tool_map import (
    DEFAULT_ABSTRACT_TOOLS,
    to_abstract_tools,
    to_claude_tools,
)
from forge_os.adapters.registry import AdapterRegistryError, get_adapter_registry
from forge_os.agents.models import AgentDefinition
from forge_os.events.store import EventStore

# ── Fixtures ─────────────────────────────────────────────────────────────────
#
# Real claude `--output-format stream-json` envelopes (verified against 2.1.x):
# system/init, assistant (text + tool_use blocks), user (tool_result), result.


def _init() -> str:
    return json.dumps(
        {"type": "system", "subtype": "init", "session_id": "s1", "model": "claude-opus-4-8"}
    )


def _assistant(*blocks: dict) -> str:
    return json.dumps(
        {"type": "assistant", "session_id": "s1",
         "message": {"role": "assistant", "content": list(blocks)}}
    )


def _text(text: str) -> dict:
    return {"type": "text", "text": text}


def _tool_use(tool_id: str, name: str, **inp: object) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": inp}


def _user_tool_result(tool_id: str, content: str) -> str:
    block = {"type": "tool_result", "tool_use_id": tool_id, "content": content}
    return json.dumps(
        {"type": "user", "session_id": "s1", "message": {"role": "user", "content": [block]}}
    )


def _result(text: str, *, is_error: bool = False, subtype: str = "success") -> str:
    return json.dumps(
        {"type": "result", "subtype": subtype, "is_error": is_error, "session_id": "s1",
         "result": text, "num_turns": 2,
         "usage": {"input_tokens": 100, "output_tokens": 20}, "total_cost_usd": 0.01}
    )


FIXTURE_STREAM_JSON = "\n".join([
    _init(),
    _assistant(_text("Analyzing the codebase..."), _tool_use("t1", "Read", file_path="SRS.md")),
    _user_tool_result("t1", "# SRS content"),
    _assistant(_text("Done. Produced SRS.md.")),
    _result("Done. Produced SRS.md."),
])

FIXTURE_STREAM_JSON_ERROR = "\n".join([
    _assistant(_text("Trying...")),
    _result("rate limited", is_error=True, subtype="error_during_execution"),
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
    return ClaudeCodeAdapter(project_root, claude_bin="claude", timeout=30)


def _make_proc(stdout: str = "", stderr: str = "", returncode: int = 0) -> MagicMock:
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


class _BoomStore(EventStore):
    """EventStore whose every append raises — exercises best-effort recording."""

    def __init__(self) -> None:
        super().__init__(Path("/nonexistent/events.db"))

    def append(self, *args: object, **kwargs: object) -> int:
        raise RuntimeError("store down")


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
    def test_parses_assistant_text(self) -> None:
        events = list(_parse_stream_lines(FIXTURE_STREAM_JSON))
        assistant = [e for e in events if e.type == "assistant"]
        assert len(assistant) == 2
        assert assistant[0].text == "Analyzing the codebase..."
        assert assistant[1].text == "Done. Produced SRS.md."

    def test_parses_tool_use_blocks(self) -> None:
        events = list(_parse_stream_lines(FIXTURE_STREAM_JSON))
        blocks = [b for e in events for b in e.tool_use_blocks]
        assert len(blocks) == 1
        assert blocks[0]["name"] == "Read"
        assert blocks[0]["input"] == {"file_path": "SRS.md"}

    def test_non_message_lines_have_no_text(self) -> None:
        events = list(_parse_stream_lines(FIXTURE_STREAM_JSON))
        init = next(e for e in events if e.type == "system")
        assert init.text == ""
        assert init.tool_use_blocks == []

    def test_skips_blank_lines(self) -> None:
        raw = "\n".join(["", _assistant(_text("hello")), "   ", _assistant(_text("world"))])
        assert len(list(_parse_stream_lines(raw))) == 2

    def test_empty_input_yields_no_events(self) -> None:
        assert list(_parse_stream_lines("")) == []
        assert list(_parse_stream_lines("   \n\n  ")) == []

    def test_skips_malformed_and_non_object_json(self) -> None:
        raw = "\n".join([_assistant(_text("ok")), "not json", "[1, 2, 3]", '"a string"'])
        assert len(list(_parse_stream_lines(raw))) == 1  # only the assistant object

    def test_text_output_is_the_final_result(self) -> None:
        result = RunResult(returncode=0, events=list(_parse_stream_lines(FIXTURE_STREAM_JSON)))
        # the agent's final answer is the result line, not intermediate turns
        assert result.text_output == "Done. Produced SRS.md."

    def test_text_output_falls_back_to_assistant_without_result(self) -> None:
        result = RunResult(returncode=0, events=list(_parse_stream_lines(_assistant(_text("hi")))))
        assert result.text_output == "hi"

    def test_run_result_tool_uses(self) -> None:
        result = RunResult(returncode=0, events=list(_parse_stream_lines(FIXTURE_STREAM_JSON)))
        assert len(result.tool_uses) == 1
        assert result.tool_uses[0]["name"] == "Read"

    def test_run_result_usage_and_cost(self) -> None:
        result = RunResult(returncode=0, events=list(_parse_stream_lines(FIXTURE_STREAM_JSON)))
        assert result.usage == {"input_tokens": 100, "output_tokens": 20}
        assert result.total_cost_usd == 0.01

    def test_result_is_error_marks_failure(self) -> None:
        events = list(_parse_stream_lines(FIXTURE_STREAM_JSON_ERROR))
        result = RunResult(returncode=0, events=events)
        assert result.is_error is True
        assert result.succeeded is False

    def test_success_result_succeeds(self) -> None:
        result = RunResult(returncode=0, events=list(_parse_stream_lines(FIXTURE_STREAM_JSON)))
        assert result.succeeded is True


# ── Real kernel output (gold-standard capture from claude 2.1.x) ──────────────


class TestRealKernelFixture:
    """Parses an actual `claude -p --output-format stream-json --verbose` capture,
    so the parser is validated against ground truth — not just synthetic fixtures."""

    GOLD = Path(__file__).parent / "fixtures" / "claude_code" / "real_text_run.jsonl"

    def test_parses_real_captured_output(self) -> None:
        result = RunResult(returncode=0, events=list(_parse_stream_lines(self.GOLD.read_text())))
        assert result.succeeded is True
        assert result.text_output == "ok"
        assert result.usage  # the real result line carries token usage
        assert result.total_cost_usd is not None

    def test_real_capture_line_types(self) -> None:
        events = list(_parse_stream_lines(self.GOLD.read_text()))
        assert [e.type for e in events] == ["system", "assistant", "result"]


# ── Slice 4: registry factory selection (binary check + model) ────────────────


class TestClaudeCodeFactory:
    def test_selection_raises_when_binary_missing(self, tmp_path: Path) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(AdapterRegistryError, match="binary on PATH"):
                get_adapter_registry().create("claude_code", tmp_path, {})

    def test_selection_builds_when_binary_present(self, tmp_path: Path) -> None:
        with patch("shutil.which", return_value="/usr/bin/claude"):
            adapter = get_adapter_registry().create(
                "claude_code", tmp_path, {"model": "claude-sonnet-4-6"}
            )
        assert isinstance(adapter, ClaudeCodeAdapter)
        assert adapter.model == "claude-sonnet-4-6"

    def test_selection_has_no_model_by_default(self, tmp_path: Path) -> None:
        with patch("shutil.which", return_value="/usr/bin/claude"):
            adapter = get_adapter_registry().create("claude_code", tmp_path, {})
        assert adapter.model is None  # type: ignore[attr-defined]

    def test_selection_honours_custom_claude_bin(self, tmp_path: Path) -> None:
        with patch("shutil.which", return_value="/opt/claude") as which:
            adapter = get_adapter_registry().create(
                "claude_code", tmp_path, {"claude_bin": "claude-next"}
            )
        which.assert_called_with("claude-next")
        assert adapter.claude_bin == "claude-next"  # type: ignore[attr-defined]


# ── Slice 4: runner --model flag ──────────────────────────────────────────────


class TestRunnerModel:
    def test_model_adds_flag(self) -> None:
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)) as mock_run:
            run_claude("p", allowed_tools=["Read"], cwd=Path("."), model="claude-sonnet-4-6")
        cmd = mock_run.call_args[0][0]
        assert cmd[cmd.index("--model") + 1] == "claude-sonnet-4-6"

    def test_no_model_means_no_flag(self) -> None:
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)) as mock_run:
            run_claude("p", allowed_tools=["Read"], cwd=Path("."))
        assert "--model" not in mock_run.call_args[0][0]


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
        assert "Done. Produced SRS.md." in handle.outputs[0].description

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

    def test_handle_metadata_has_run_id(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            handle = adapter.spawn_agent(persona, "context", ["read_file"])
        assert handle.metadata["run_id"].startswith("ccrun-")


# ── Slice 2: runner on_event callback ────────────────────────────────────────


class TestRunnerOnEvent:
    def test_on_event_called_for_every_stream_line(self) -> None:
        seen: list[StreamEvent] = []
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            run_claude("p", allowed_tools=["Read"], cwd=Path("."), on_event=seen.append)
        # FIXTURE has 5 lines: init, assistant(+tool_use), user(tool_result), assistant, result
        assert [e.type for e in seen] == ["system", "assistant", "user", "assistant", "result"]

    def test_on_event_fires_before_failure(self) -> None:
        seen: list[StreamEvent] = []
        error_proc = _make_proc(FIXTURE_STREAM_JSON_ERROR, returncode=0)
        with patch("subprocess.run", return_value=error_proc):
            with pytest.raises(ClaudeCodeSpawnError):
                run_claude("p", allowed_tools=["Read"], cwd=Path("."), on_event=seen.append)
        # both lines were recorded before run_claude raised
        assert [e.type for e in seen] == ["assistant", "result"]

    def test_on_event_optional(self) -> None:
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            result = run_claude("p", allowed_tools=["Read"], cwd=Path("."))
        assert len(result.events) == 5


# ── Slice 2: event-store recording ───────────────────────────────────────────


class TestEventStoreRecording:
    @pytest.fixture
    def event_store(self, tmp_path: Path) -> EventStore:
        return EventStore(tmp_path / "events.db")

    @pytest.fixture
    def recording_adapter(
        self, project_root: Path, event_store: EventStore
    ) -> ClaudeCodeAdapter:
        return ClaudeCodeAdapter(project_root, event_store=event_store, timeout=30)

    def test_records_started_streams_completed_in_order(
        self,
        recording_adapter: ClaudeCodeAdapter,
        persona: AgentDefinition,
        event_store: EventStore,
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            handle = recording_adapter.spawn_agent(persona, "ctx", ["read_file", "write_file"])

        run_id = handle.metadata["run_id"]
        types = [e["event_type"] for e in event_store.read_stream(run_id)]
        assert len(types) == 7  # started + 5 stream lines + completed
        assert types[0] == EVENT_SPAWN_STARTED
        assert types[-1] == EVENT_SPAWN_COMPLETED
        assert types.count(EVENT_STREAM) == 5  # one per stream-json line

    def test_started_payload_captures_persona_and_tools(
        self,
        recording_adapter: ClaudeCodeAdapter,
        persona: AgentDefinition,
        event_store: EventStore,
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            handle = recording_adapter.spawn_agent(persona, "ctx", ["read_file"])

        run_id = handle.metadata["run_id"]
        started = next(
            json.loads(e["payload"])
            for e in event_store.read_stream(run_id)
            if e["event_type"] == EVENT_SPAWN_STARTED
        )
        assert started["persona_id"] == "srs-agent"
        assert started["stage_id"] == "srs"
        assert started["granted_tools"] == ["read_file"]
        assert started["claude_tools"] == ["Read"]
        assert started["context"] == "ctx"
        assert "Software architect" in started["prompt"]

    def test_stream_payload_preserves_raw_line(
        self,
        recording_adapter: ClaudeCodeAdapter,
        persona: AgentDefinition,
        event_store: EventStore,
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            handle = recording_adapter.spawn_agent(persona, "ctx", ["read_file"])

        run_id = handle.metadata["run_id"]
        streams = [
            json.loads(e["payload"])
            for e in event_store.read_stream(run_id)
            if e["event_type"] == EVENT_STREAM
        ]
        assistant = next(
            s for s in streams
            if s["type"] == "assistant"
            and any(b.get("type") == "tool_use" for b in s["raw"]["message"]["content"])
        )
        content = assistant["raw"]["message"]["content"]
        tool_use = next(b for b in content if b["type"] == "tool_use")
        assert tool_use["name"] == "Read"
        assert tool_use["input"] == {"file_path": "SRS.md"}

    def test_completed_payload(
        self,
        recording_adapter: ClaudeCodeAdapter,
        persona: AgentDefinition,
        event_store: EventStore,
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            handle = recording_adapter.spawn_agent(persona, "ctx", ["read_file"])

        run_id = handle.metadata["run_id"]
        completed = next(
            json.loads(e["payload"])
            for e in event_store.read_stream(run_id)
            if e["event_type"] == EVENT_SPAWN_COMPLETED
        )
        assert completed["status"] == "completed"
        assert completed["returncode"] == 0
        assert completed["tool_use_count"] == 1

    def test_failed_run_records_started_and_failed_no_completed(
        self,
        recording_adapter: ClaudeCodeAdapter,
        persona: AgentDefinition,
        event_store: EventStore,
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc("", "Boom", 1)):
            with pytest.raises(ClaudeCodeSpawnError):
                recording_adapter.spawn_agent(persona, "ctx", ["read_file"])

        assert len(event_store.read_by_type(EVENT_SPAWN_STARTED)) == 1
        failed = event_store.read_by_type(EVENT_SPAWN_FAILED)
        assert len(failed) == 1
        payload = json.loads(failed[0]["payload"])
        assert payload["returncode"] == 1
        assert "Boom" in payload["error"]
        assert event_store.read_by_type(EVENT_SPAWN_COMPLETED) == []

    def test_failed_run_still_records_stream_lines(
        self,
        recording_adapter: ClaudeCodeAdapter,
        persona: AgentDefinition,
        event_store: EventStore,
    ) -> None:
        # returncode 0 but stream contains an error line → ClaudeCodeSpawnError
        error_proc = _make_proc(FIXTURE_STREAM_JSON_ERROR, returncode=0)
        with patch("subprocess.run", return_value=error_proc):
            with pytest.raises(ClaudeCodeSpawnError):
                recording_adapter.spawn_agent(persona, "ctx", ["read_file"])

        streams = [json.loads(e["payload"]) for e in event_store.read_by_type(EVENT_STREAM)]
        assert [s["type"] for s in streams] == ["assistant", "result"]
        result_line = next(s for s in streams if s["type"] == "result")
        assert result_line["raw"]["result"] == "rate limited"
        assert result_line["raw"]["is_error"] is True
        assert len(event_store.read_by_type(EVENT_SPAWN_FAILED)) == 1

    def test_no_event_store_means_no_recording(
        self, project_root: Path, persona: AgentDefinition
    ) -> None:
        adapter = ClaudeCodeAdapter(project_root)  # no event_store injected
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            handle = adapter.spawn_agent(persona, "ctx", ["read_file"])
        assert handle.metadata["run_id"].startswith("ccrun-")  # run_id still assigned

    def test_no_event_store_failure_still_raises(
        self, project_root: Path, persona: AgentDefinition
    ) -> None:
        adapter = ClaudeCodeAdapter(project_root)  # no event_store injected
        with patch("subprocess.run", return_value=_make_proc("", "Boom", 1)):
            with pytest.raises(ClaudeCodeSpawnError):
                adapter.spawn_agent(persona, "ctx", ["read_file"])

    def test_empty_stream_records_started_and_completed_only(
        self,
        recording_adapter: ClaudeCodeAdapter,
        persona: AgentDefinition,
        event_store: EventStore,
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc("")):
            handle = recording_adapter.spawn_agent(persona, "ctx", ["read_file"])

        run_id = handle.metadata["run_id"]
        types = [e["event_type"] for e in event_store.read_stream(run_id)]
        assert types == [EVENT_SPAWN_STARTED, EVENT_SPAWN_COMPLETED]  # zero stream events

    def test_sequential_spawns_get_distinct_run_ids(
        self,
        recording_adapter: ClaudeCodeAdapter,
        persona: AgentDefinition,
        event_store: EventStore,
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            run1 = recording_adapter.spawn_agent(persona, "ctx", ["read_file"]).metadata["run_id"]
            run2 = recording_adapter.spawn_agent(persona, "ctx", ["read_file"]).metadata["run_id"]

        assert run1 != run2
        assert event_store.read_stream(run1)[0]["event_type"] == EVENT_SPAWN_STARTED
        assert len(event_store.read_by_type(EVENT_SPAWN_STARTED)) == 2

    def test_event_store_failure_does_not_abort_successful_spawn(
        self, project_root: Path, persona: AgentDefinition
    ) -> None:
        adapter = ClaudeCodeAdapter(project_root, event_store=_BoomStore())
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            handle = adapter.spawn_agent(persona, "ctx", ["read_file"])
        # recording failed silently (best-effort) but the spawn still completed
        assert handle.status == "completed"
        assert handle.metadata["run_id"].startswith("ccrun-")

    def test_event_store_failure_does_not_mask_spawn_error(
        self, project_root: Path, persona: AgentDefinition
    ) -> None:
        adapter = ClaudeCodeAdapter(project_root, event_store=_BoomStore())
        with patch("subprocess.run", return_value=_make_proc("", "Boom", 1)):
            # the original ClaudeCodeSpawnError must surface, not the store error
            with pytest.raises(ClaudeCodeSpawnError):
                adapter.spawn_agent(persona, "ctx", ["read_file"])


# ── Slice 2: hook lifecycle ──────────────────────────────────────────────────


class TestAdapterHookLifecycle:
    def test_hooks_present_during_spawn_and_torn_down_after(
        self, project_root: Path, persona: AgentDefinition
    ) -> None:
        adapter = ClaudeCodeAdapter(project_root, hook_command="forge hook tool")
        observed: dict[str, bool] = {}

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            settings = project_root / ".claude" / "settings.json"
            observed["existed_during_run"] = settings.exists()
            return _make_proc(FIXTURE_STREAM_JSON)

        with patch("subprocess.run", side_effect=fake_run):
            adapter.spawn_agent(persona, "ctx", ["read_file"])

        assert observed["existed_during_run"] is True
        assert not (project_root / ".claude").exists()  # torn down

    def test_hooks_torn_down_even_when_spawn_fails(
        self, project_root: Path, persona: AgentDefinition
    ) -> None:
        adapter = ClaudeCodeAdapter(project_root, hook_command="forge hook tool")
        with patch("subprocess.run", return_value=_make_proc("", "fail", 1)):
            with pytest.raises(ClaudeCodeSpawnError):
                adapter.spawn_agent(persona, "ctx", ["read_file"])
        assert not (project_root / ".claude").exists()

    def test_no_hook_command_creates_no_claude_dir(
        self, project_root: Path, persona: AgentDefinition
    ) -> None:
        adapter = ClaudeCodeAdapter(project_root)
        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            adapter.spawn_agent(persona, "ctx", ["read_file"])
        assert not (project_root / ".claude").exists()

    def test_hook_install_failure_records_terminal_failed_event(
        self, project_root: Path, persona: AgentDefinition
    ) -> None:
        # A malformed pre-existing settings.json makes hook install raise; the
        # spawn must surface that error AND record a terminal Failed event
        # (never an orphaned Started with no terminal).
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text("{not json", encoding="utf-8")
        store = EventStore(project_root / "events.db")
        adapter = ClaudeCodeAdapter(
            project_root, event_store=store, hook_command="forge hook tool"
        )

        with patch("subprocess.run", return_value=_make_proc(FIXTURE_STREAM_JSON)):
            with pytest.raises(ClaudeSettingsError):
                adapter.spawn_agent(persona, "ctx", ["read_file"])

        assert len(store.read_by_type(EVENT_SPAWN_STARTED)) == 1
        assert len(store.read_by_type(EVENT_SPAWN_FAILED)) == 1
        assert store.read_by_type(EVENT_SPAWN_COMPLETED) == []
