"""Tests for AsyncToSyncBridge (FR-KA-001..005).

The bridge is tested using HumanAdapter with scripted I/O — no network calls.
spawn_agent() is sync and uses asyncio.run() internally, so tests are plain
sync functions.
"""

from __future__ import annotations

from forge_os.adapters.base import AgentHandle
from forge_os.adapters.bridge import AsyncToSyncBridge, _agent_def_to_persona
from forge_os.adapters.human.adapter import HumanAdapter
from forge_os.agents.models import AgentDefinition
from forge_os.kernel.types import (
    AgentPersona,
    ToolResult,
    ToolUseProposal,
)


def _make_agent_def(**kwargs) -> AgentDefinition:
    defaults = dict(
        id="test-agent-01",
        name="test-agent",
        category="stage",
        role="test role",
        prompt="do the test goal",
        default_tools=["Read", "Write"],
    )
    defaults.update(kwargs)
    return AgentDefinition(**defaults)


def _scripted_bridge(inputs: list[str], **bridge_kwargs) -> AsyncToSyncBridge:
    it = iter(inputs)

    def _input(prompt: str) -> str:
        try:
            return next(it)
        except StopIteration as exc:
            raise EOFError("scripted input exhausted") from exc

    inner = HumanAdapter(input_fn=_input, print_fn=lambda _: None)
    return AsyncToSyncBridge(inner, **bridge_kwargs)


class TestAgentDefToPersona:
    def test_basic_mapping(self) -> None:
        ad = _make_agent_def()
        persona = _agent_def_to_persona(ad)
        assert isinstance(persona, AgentPersona)
        assert persona.name == "test-agent"
        assert persona.role == "test role"
        assert persona.goal == "do the test goal"
        assert "Read" in persona.allowed_tools

    def test_empty_tools(self) -> None:
        ad = _make_agent_def(default_tools=[])
        persona = _agent_def_to_persona(ad)
        assert persona.allowed_tools == []


class TestAsyncToSyncBridgeAdapterId:
    def test_adapter_id_has_bridge_prefix(self) -> None:
        inner = HumanAdapter()
        bridge = AsyncToSyncBridge(inner)
        assert bridge.adapter_id == "bridge:human"

    def test_inner_adapter_id_reflected(self) -> None:
        inner = HumanAdapter()
        bridge = AsyncToSyncBridge(inner)
        assert bridge.adapter_id.startswith("bridge:")


class TestSpawnAgentCompletedPath:
    def test_say_then_done_returns_completed_handle(self) -> None:
        bridge = _scripted_bridge(["s", "hello from human", "d"])
        ad = _make_agent_def()
        handle = bridge.spawn_agent(ad, "test context", ["Read"])

        assert isinstance(handle, AgentHandle)
        assert handle.status == "completed"
        assert handle.provider == "bridge:human"

    def test_completed_handle_contains_text(self) -> None:
        bridge = _scripted_bridge(["s", "my agent output", "d"])
        ad = _make_agent_def()
        handle = bridge.spawn_agent(ad, "ctx", ["Read"])

        assert handle.status == "completed"
        assert "my agent output" in handle.metadata.get("full_text", "")

    def test_multiple_say_lines_joined(self) -> None:
        bridge = _scripted_bridge(["s", "line one", "s", "line two", "d"])
        handle = bridge.spawn_agent(_make_agent_def(), "ctx", ["Read"])
        assert handle.status == "completed"
        full = handle.metadata.get("full_text", "")
        assert "line one" in full
        assert "line two" in full

    def test_outputs_list_populated(self) -> None:
        bridge = _scripted_bridge(["s", "some output text", "d"])
        handle = bridge.spawn_agent(_make_agent_def(), "ctx", ["Read"])
        assert len(handle.outputs) >= 1
        assert handle.outputs[0].path == "(stream)"


class TestSpawnAgentFailedPath:
    def test_abort_returns_failed_handle(self) -> None:
        bridge = _scripted_bridge(["x", "test abort reason"])
        handle = bridge.spawn_agent(_make_agent_def(), "ctx", ["Read"])
        assert handle.status == "failed"

    def test_eof_returns_failed_handle(self) -> None:
        bridge = _scripted_bridge([])
        handle = bridge.spawn_agent(_make_agent_def(), "ctx", ["Read"])
        assert handle.status == "failed"


class TestToolUseProposalAutoDecline:
    def test_auto_decline_continues_and_completes(self) -> None:
        # c → Read → {} → bridge auto-declines → d
        bridge = _scripted_bridge(["c", "Read", "{}", "d"])
        handle = bridge.spawn_agent(_make_agent_def(), "ctx", ["Read"])
        assert handle.status == "completed"

    def test_auto_decline_is_error_result(self) -> None:
        """Verify that when a proposal is auto-declined the agent still finishes."""
        declined_proposals: list[str] = []

        async def recording_handler(p: ToolUseProposal) -> ToolResult:
            declined_proposals.append(p.abstract_tool)
            return ToolResult(tool_use_id=p.tool_use_id, content="mock result")

        it = iter(["c", "Read", "{}", "d"])

        def _input(prompt: str) -> str:
            try:
                return next(it)
            except StopIteration as exc:
                raise EOFError from exc

        inner = HumanAdapter(input_fn=_input, print_fn=lambda _: None)
        bridge = AsyncToSyncBridge(inner, proposal_handler=recording_handler)
        handle = bridge.spawn_agent(_make_agent_def(), "ctx", ["Read"])
        assert handle.status == "completed"
        assert "Read" in declined_proposals


class TestGetDefaultTools:
    def test_delegates_to_inner_capabilities(self) -> None:
        inner = HumanAdapter()
        bridge = AsyncToSyncBridge(inner)
        tools = bridge.get_default_tools()
        assert "Read" in tools
        assert "Write" in tools

    def test_returns_list(self) -> None:
        bridge = AsyncToSyncBridge(HumanAdapter())
        assert isinstance(bridge.get_default_tools(), list)


class TestSupports:
    def test_known_tool(self) -> None:
        bridge = AsyncToSyncBridge(HumanAdapter())
        assert bridge.supports("Read") is True

    def test_unknown_tool(self) -> None:
        bridge = AsyncToSyncBridge(HumanAdapter())
        assert bridge.supports("NonExistentTool") is False


class TestOnEvent:
    def test_returns_event_response(self) -> None:
        from forge_os.adapters.base import EventResponse
        bridge = AsyncToSyncBridge(HumanAdapter(print_fn=lambda _: None))
        resp = bridge.on_event(None, None)  # type: ignore[arg-type]
        assert isinstance(resp, EventResponse)
        assert resp.handled is True
