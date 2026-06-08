"""Tests for forge_os.kernel.types canonical shared types (FR-KA-001..005)."""

from __future__ import annotations

import pytest

from forge_os.kernel.types import (
    AgentPersona,
    EventKind,
    IKernelAdapter,
    KernelCapabilities,
    NormalizedEvent,
    ToolResult,
    ToolUseProposal,
)


class TestEventKind:
    def test_all_expected_values(self) -> None:
        values = {e.value for e in EventKind}
        assert "session_started" in values
        assert "text_delta" in values
        assert "tool_use_proposed" in values
        assert "agent_completed" in values
        assert "agent_failed" in values

    def test_is_str(self) -> None:
        assert isinstance(EventKind.TEXT_DELTA, str)
        assert EventKind.TEXT_DELTA == "text_delta"

    def test_codex_specific_kinds(self) -> None:
        assert EventKind.PLAN_UPDATED == "plan_updated"
        assert EventKind.DIFF_UPDATED == "diff_updated"


class TestNormalizedEvent:
    def test_construction(self) -> None:
        ev = NormalizedEvent(kind=EventKind.SESSION_STARTED, aggregate_id="agg-1")
        assert ev.kind == EventKind.SESSION_STARTED
        assert ev.aggregate_id == "agg-1"
        assert ev.payload == {}

    def test_with_payload(self) -> None:
        ev = NormalizedEvent(
            kind=EventKind.TEXT_DELTA,
            aggregate_id="agg-2",
            payload={"text": "hello"},
        )
        assert ev.payload["text"] == "hello"


class TestToolUseProposal:
    def test_is_normalized_event(self) -> None:
        proposal = ToolUseProposal(
            kind=EventKind.TOOL_USE_PROPOSED,
            aggregate_id="agg-3",
            tool_use_id="tu-001",
            tool_name="bash",
            abstract_tool="Bash",
            inputs={"command": "ls"},
        )
        assert isinstance(proposal, NormalizedEvent)
        assert proposal.abstract_tool == "Bash"
        assert proposal.inputs == {"command": "ls"}

    def test_default_inputs(self) -> None:
        p = ToolUseProposal(
            kind=EventKind.TOOL_USE_PROPOSED, aggregate_id="x"
        )
        assert p.inputs == {}
        assert p.tool_use_id == ""


class TestToolResult:
    def test_string_content(self) -> None:
        r = ToolResult(tool_use_id="tu-1", content="ok")
        assert r.content == "ok"
        assert r.is_error is False

    def test_error_result(self) -> None:
        r = ToolResult(tool_use_id="tu-2", content="boom", is_error=True)
        assert r.is_error is True

    def test_list_content(self) -> None:
        r = ToolResult(tool_use_id="tu-3", content=[{"type": "text", "text": "hi"}])
        assert isinstance(r.content, list)


class TestAgentPersona:
    def test_defaults(self) -> None:
        p = AgentPersona(name="a", role="r", goal="g")
        assert p.constraints == []
        assert p.allowed_tools == []
        assert p.preferred_model == "claude-opus-4-7"
        assert p.temperature == 0.0
        assert p.thinking_budget_tokens is None
        assert p.enable_skills is False

    def test_full_construction(self) -> None:
        p = AgentPersona(
            name="architect",
            role="System Architect",
            goal="Design event store schema",
            constraints=["No prose"],
            allowed_tools=["Read", "Write"],
            preferred_model="claude-sonnet-4-6",
            max_tokens=8192,
            thinking_budget_tokens=2048,
        )
        assert p.name == "architect"
        assert "Read" in p.allowed_tools
        assert p.thinking_budget_tokens == 2048


class TestKernelCapabilities:
    def test_construction(self) -> None:
        caps = KernelCapabilities(
            kernel_id="test",
            streaming=True,
            deterministic_output=False,
            extended_thinking=False,
            prompt_caching=False,
            vision=False,
            batch_api=False,
            hooks_native=False,
            subagents_native=False,
            mcp_remote=False,
            mcp_local_stdio=False,
            client_tools=["Read"],
            server_tools=[],
            max_context_tokens=8192,
        )
        assert caps.kernel_id == "test"
        assert caps.client_tools == ["Read"]
        assert caps.notes == {}


class TestIKernelAdapterABC:
    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            IKernelAdapter()  # type: ignore[abstract]

    def test_concrete_must_implement_all_methods(self) -> None:
        class Incomplete(IKernelAdapter):
            def get_capabilities(self): ...  # type: ignore[override]
            # missing spawn_agent, on_event, sync_memory

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]
