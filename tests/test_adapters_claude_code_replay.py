"""Tests for ClaudeCodeAdapter replay (Slice 3) — reconstruct a handle from the
Event Store with no subprocess invocation (FR-ES-003 / ADR-005)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forge_os.adapters.claude_code import (
    ClaudeCodeAdapter,
    ClaudeCodeSpawnError,
    ReplayError,
    replay_session,
)
from forge_os.adapters.claude_code.adapter import (
    EVENT_SPAWN_COMPLETED,
    EVENT_SPAWN_FAILED,
    EVENT_SPAWN_STARTED,
    EVENT_STREAM,
)
from forge_os.agents.models import AgentDefinition
from forge_os.events.store import EventStore

_TEXT1 = {"type": "text", "text": "Analyzing the codebase..."}
_TOOL = {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "x"}}
_TOOL_RESULT = {"type": "tool_result", "tool_use_id": "t1", "content": "# SRS content"}
_TEXT2 = {"type": "text", "text": "Done. Produced SRS.md."}


def _assistant(*blocks: dict) -> str:
    return json.dumps(
        {"type": "assistant", "session_id": "s1",
         "message": {"role": "assistant", "content": list(blocks)}}
    )


FIXTURE_STREAM_JSON = "\n".join([
    json.dumps({"type": "system", "subtype": "init", "session_id": "s1"}),
    _assistant(_TEXT1, _TOOL),
    json.dumps({"type": "user", "session_id": "s1",
                "message": {"role": "user", "content": [_TOOL_RESULT]}}),
    _assistant(_TEXT2),
    json.dumps({"type": "result", "subtype": "success", "is_error": False, "session_id": "s1",
                "result": "Done. Produced SRS.md.",
                "usage": {"input_tokens": 100, "output_tokens": 20}, "total_cost_usd": 0.01}),
])


def _make_proc(stdout: str = "", stderr: str = "", returncode: int = 0) -> MagicMock:
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


@pytest.fixture
def event_store(tmp_path: Path) -> EventStore:
    return EventStore(tmp_path / "events.db")


@pytest.fixture
def adapter(tmp_path: Path, event_store: EventStore) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter(tmp_path / "proj", event_store=event_store, timeout=30)


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


def _record_a_spawn(
    adapter: ClaudeCodeAdapter, persona: AgentDefinition, stdout: str = FIXTURE_STREAM_JSON
):
    """Run one spawn (subprocess mocked) and return the original handle."""
    with patch("subprocess.run", return_value=_make_proc(stdout)):
        return adapter.spawn_agent(persona, "build the SRS", ["read_file", "write_file"])


# ── Happy-path replay ─────────────────────────────────────────────────────────


class TestReplaySuccess:
    def test_replay_does_not_invoke_subprocess(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        original = _record_a_spawn(adapter, persona)
        run_id = original.metadata["run_id"]

        with patch("subprocess.run") as mock_run:
            adapter.replay_session(run_id)
        mock_run.assert_not_called()

    def test_replay_equals_original_handle(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        original = _record_a_spawn(adapter, persona)
        replayed = adapter.replay_session(original.metadata["run_id"])
        assert replayed == original

    def test_replay_reconstructs_fields(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        original = _record_a_spawn(adapter, persona)
        replayed = adapter.replay_session(original.metadata["run_id"])
        assert replayed.provider == "claude-code"
        assert replayed.persona_id == "srs-agent"
        assert replayed.stage_id == "srs"
        assert replayed.status == "completed"
        assert replayed.handle_id == original.handle_id

    def test_replay_outputs_reconstructed_from_stream(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        original = _record_a_spawn(adapter, persona)
        replayed = adapter.replay_session(original.metadata["run_id"])
        assert len(replayed.outputs) == 1
        assert "Done. Produced SRS.md." in replayed.outputs[0].description

    def test_replay_metadata_matches(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        original = _record_a_spawn(adapter, persona)
        replayed = adapter.replay_session(original.metadata["run_id"])
        assert replayed.metadata == original.metadata

    def test_replay_is_deterministic(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        original = _record_a_spawn(adapter, persona)
        run_id = original.metadata["run_id"]
        # Determinism comes from reading committed events, never re-running the
        # kernel (ADR-005): two replays of the same run_id are identical.
        first = adapter.replay_session(run_id)
        second = adapter.replay_session(run_id)
        assert first == second
        assert first.handle_id == second.handle_id

    def test_replay_from_handcrafted_events_projects_from_store(
        self, adapter: ClaudeCodeAdapter, event_store: EventStore
    ) -> None:
        # Hand-craft a run directly in the store (no spawn): replay must project
        # outputs FROM the recorded stream events, proving it reads the store.
        run_id = "ccrun-handcrafted"
        event_store.append(
            run_id, EVENT_SPAWN_STARTED,
            {"adapter": "claude-code", "persona_id": "p1", "stage_id": "srs"},
        )
        for word in ("Hello", "World"):
            event_store.append(
                run_id, EVENT_STREAM,
                {"type": "assistant",
                 "raw": {"type": "assistant",
                         "message": {"content": [{"type": "text", "text": word}]}}},
            )
        event_store.append(
            run_id, EVENT_SPAWN_COMPLETED,
            {"adapter": "claude-code", "handle_id": "h-xyz", "status": "completed",
             "returncode": 0, "metadata": {"run_id": run_id}},
        )
        handle = adapter.replay_session(run_id)
        assert handle.handle_id == "h-xyz"
        assert handle.persona_id == "p1"
        assert handle.stage_id == "srs"
        assert handle.outputs[0].description == "Hello\nWorld"
        assert handle.metadata == {"run_id": run_id}

    def test_replay_empty_stream_has_no_outputs(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition
    ) -> None:
        original = _record_a_spawn(adapter, persona, stdout="")
        replayed = adapter.replay_session(original.metadata["run_id"])
        assert replayed.outputs == []
        assert replayed == original

    def test_module_function_matches_method(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition, event_store: EventStore
    ) -> None:
        original = _record_a_spawn(adapter, persona)
        run_id = original.metadata["run_id"]
        assert replay_session(event_store, run_id) == original


# ── Error paths ───────────────────────────────────────────────────────────────


class TestReplayErrors:
    def test_unknown_run_id_raises(self, adapter: ClaudeCodeAdapter) -> None:
        with pytest.raises(ReplayError, match="no recorded run"):
            adapter.replay_session("ccrun-does-not-exist")

    def test_failed_run_raises_with_details(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition, event_store: EventStore
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc("", "Boom", 1)):
            with pytest.raises(ClaudeCodeSpawnError):
                adapter.spawn_agent(persona, "ctx", ["read_file"])
        # the failed run recorded a started event; find its run_id (stream id)
        run_id = event_store.read_by_type(EVENT_SPAWN_STARTED)[0]["stream_id"]
        with pytest.raises(ReplayError, match="failed"):
            adapter.replay_session(run_id)

    def test_incomplete_run_raises(
        self, adapter: ClaudeCodeAdapter, event_store: EventStore
    ) -> None:
        # Only a start event recorded — no terminal event.
        event_store.append(
            "ccrun-partial", EVENT_SPAWN_STARTED, {"adapter": "claude-code", "persona_id": "p"}
        )
        with pytest.raises(ReplayError, match="incomplete"):
            adapter.replay_session("ccrun-partial")

    def test_run_without_start_event_raises(
        self, adapter: ClaudeCodeAdapter, event_store: EventStore
    ) -> None:
        event_store.append("ccrun-nostart", "AdapterStreamEvent", {"type": "text", "raw": {}})
        with pytest.raises(ReplayError, match="no start event"):
            adapter.replay_session("ccrun-nostart")

    def test_no_event_store_raises(self, tmp_path: Path) -> None:
        adapter = ClaudeCodeAdapter(tmp_path)  # no event_store injected
        with pytest.raises(ReplayError, match="no event store"):
            adapter.replay_session("ccrun-anything")

    def test_failed_event_without_start_raises_no_start(
        self, adapter: ClaudeCodeAdapter, event_store: EventStore
    ) -> None:
        # A terminal-failure event with no start event: the no-start check fires
        # before the terminal-type check.
        event_store.append(
            "ccrun-failed-nostart", EVENT_SPAWN_FAILED,
            {"adapter": "claude-code", "returncode": 1, "error": "boom"},
        )
        with pytest.raises(ReplayError, match="no start event"):
            adapter.replay_session("ccrun-failed-nostart")

    def test_failed_run_replay_does_not_invoke_subprocess(
        self, adapter: ClaudeCodeAdapter, persona: AgentDefinition, event_store: EventStore
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc("", "Boom", 1)):
            with pytest.raises(ClaudeCodeSpawnError):
                adapter.spawn_agent(persona, "ctx", ["read_file"])
        run_id = event_store.read_by_type(EVENT_SPAWN_STARTED)[0]["stream_id"]
        with patch("subprocess.run") as mock_run:
            with pytest.raises(ReplayError):
                adapter.replay_session(run_id)
        mock_run.assert_not_called()

    def test_completed_event_missing_handle_id_raises(
        self, adapter: ClaudeCodeAdapter, event_store: EventStore
    ) -> None:
        # An AdapterSpawnCompleted from an older schema (no handle_id) yields a
        # clean ReplayError, not a raw KeyError.
        run_id = "ccrun-old-schema"
        event_store.append(
            run_id, EVENT_SPAWN_STARTED, {"adapter": "claude-code", "persona_id": "p"}
        )
        event_store.append(
            run_id, EVENT_SPAWN_COMPLETED,
            {"adapter": "claude-code", "status": "completed", "returncode": 0, "metadata": {}},
        )
        with pytest.raises(ReplayError, match="malformed or incompatible"):
            adapter.replay_session(run_id)

    def test_stream_event_missing_keys_raises(
        self, adapter: ClaudeCodeAdapter, event_store: EventStore
    ) -> None:
        run_id = "ccrun-bad-stream"
        event_store.append(
            run_id, EVENT_SPAWN_STARTED, {"adapter": "claude-code", "persona_id": "p"}
        )
        event_store.append(run_id, EVENT_STREAM, {"raw": {"content": "x"}})  # missing "type"
        event_store.append(
            run_id, EVENT_SPAWN_COMPLETED,
            {"adapter": "claude-code", "handle_id": "h", "status": "completed",
             "returncode": 0, "metadata": {}},
        )
        with pytest.raises(ReplayError, match="malformed or incompatible"):
            adapter.replay_session(run_id)
