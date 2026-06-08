"""Tests for HumanAdapter (FR-KA-001..005).

All tests use scripted I/O — no real terminal required.
"""

from __future__ import annotations

from forge_os.adapters.human.adapter import FORGE_ABSTRACT_TOOLS, HumanAdapter
from forge_os.kernel.types import (
    AgentPersona,
    EventKind,
    KernelCapabilities,
    NormalizedEvent,
    ToolResult,
    ToolUseProposal,
)


def _make_persona(**kwargs) -> AgentPersona:
    defaults = dict(name="tester", role="test role", goal="test goal",
                    allowed_tools=["Read", "Write"])
    defaults.update(kwargs)
    return AgentPersona(**defaults)


def _scripted_adapter(inputs: list[str]) -> HumanAdapter:
    """Return a HumanAdapter with a scripted input sequence."""
    it = iter(inputs)

    def _input(prompt: str) -> str:
        try:
            return next(it)
        except StopIteration as exc:
            raise EOFError("scripted input exhausted") from exc

    return HumanAdapter(input_fn=_input, print_fn=lambda _: None)


async def _drain(agen, sends: dict | None = None) -> list[NormalizedEvent]:
    """Drain an async generator, optionally auto-sending ToolResults."""
    events: list[NormalizedEvent] = []
    send_val = None
    while True:
        try:
            ev = await agen.asend(send_val)
        except StopAsyncIteration:
            break
        send_val = None
        events.append(ev)
        if isinstance(ev, ToolUseProposal) and sends:
            send_val = sends.get(ev.tool_use_id) or ToolResult(
                tool_use_id=ev.tool_use_id, content="ok"
            )
    return events


class TestGetCapabilities:
    def test_kernel_id(self) -> None:
        caps = HumanAdapter().get_capabilities()
        assert caps.kernel_id == "human"

    def test_is_kernel_capabilities(self) -> None:
        assert isinstance(HumanAdapter().get_capabilities(), KernelCapabilities)

    def test_has_abstract_tools(self) -> None:
        caps = HumanAdapter().get_capabilities()
        assert "Read" in caps.client_tools
        assert "Write" in caps.client_tools
        assert caps.server_tools == []

    def test_zero_streaming_batch(self) -> None:
        caps = HumanAdapter().get_capabilities()
        assert caps.streaming is False
        assert caps.batch_api is False


class TestSpawnAgentSimpleTurn:
    async def test_say_then_done(self) -> None:
        adapter = _scripted_adapter(["s", "hello world", "d"])
        persona = _make_persona()
        events = await _drain(adapter.spawn_agent(persona, "ctx", ["Read"], "agg-1"))

        kinds = [e.kind for e in events]
        assert EventKind.SESSION_STARTED in kinds
        assert EventKind.TEXT_DELTA in kinds
        assert EventKind.AGENT_COMPLETED in kinds

        text_evs = [e for e in events if e.kind == EventKind.TEXT_DELTA]
        assert text_evs[0].payload["text"] == "hello world"

    async def test_abort(self) -> None:
        adapter = _scripted_adapter(["x", "no thanks"])
        persona = _make_persona()
        events = await _drain(adapter.spawn_agent(persona, "ctx", ["Read"], "agg-2"))

        kinds = [e.kind for e in events]
        assert EventKind.AGENT_FAILED in kinds
        failed = next(e for e in events if e.kind == EventKind.AGENT_FAILED)
        assert "no thanks" in failed.payload["reason"]

    async def test_eof_produces_failed(self) -> None:
        # Only SESSION_STARTED then EOFError
        adapter = _scripted_adapter([])
        persona = _make_persona()
        events = await _drain(adapter.spawn_agent(persona, "ctx", ["Read"], "agg-3"))
        kinds = [e.kind for e in events]
        assert EventKind.AGENT_FAILED in kinds

    async def test_thinking_delta(self) -> None:
        adapter = _scripted_adapter(["k", "my reasoning", "d"])
        persona = _make_persona()
        events = await _drain(adapter.spawn_agent(persona, "ctx", ["Read"], "agg-4"))
        kinds = [e.kind for e in events]
        assert EventKind.THINKING_DELTA in kinds


class TestToolUseProposalHandshake:
    async def test_tool_call_then_done(self) -> None:
        # c → tool selection: Read → args: {} → receive result → d
        adapter = _scripted_adapter(["c", "Read", "{}", "d"])
        persona = _make_persona()

        events: list[NormalizedEvent] = []
        agen = adapter.spawn_agent(persona, "ctx", ["Read"], "agg-5")
        send_val = None
        while True:
            try:
                ev = await agen.asend(send_val)
            except StopAsyncIteration:
                break
            send_val = None
            events.append(ev)
            if isinstance(ev, ToolUseProposal):
                send_val = ToolResult(tool_use_id=ev.tool_use_id, content="file content")

        kinds = [e.kind for e in events]
        assert EventKind.TOOL_USE_PROPOSED in kinds
        assert EventKind.AGENT_COMPLETED in kinds

        proposal = next(e for e in events if isinstance(e, ToolUseProposal))
        assert proposal.abstract_tool == "Read"

    async def test_invalid_tool_rejected_and_retried(self) -> None:
        # First attempt: bad tool name → re-prompt → valid
        adapter = _scripted_adapter(["c", "BadTool", "Read", "{}", "d"])
        persona = _make_persona()
        agen = adapter.spawn_agent(persona, "ctx", ["Read"], "agg-6")
        send_val = None
        events: list[NormalizedEvent] = []
        while True:
            try:
                ev = await agen.asend(send_val)
            except StopAsyncIteration:
                break
            send_val = None
            events.append(ev)
            if isinstance(ev, ToolUseProposal):
                send_val = ToolResult(tool_use_id=ev.tool_use_id, content="ok")

        assert EventKind.AGENT_COMPLETED in [e.kind for e in events]


class TestOnEvent:
    async def test_no_error(self) -> None:
        adapter = HumanAdapter(print_fn=lambda _: None)
        ev = NormalizedEvent(kind=EventKind.SESSION_STARTED, aggregate_id="x")
        await adapter.on_event(ev)  # should not raise


class TestSyncMemory:
    async def test_no_op(self) -> None:
        adapter = HumanAdapter()
        await adapter.sync_memory()  # should not raise
        await adapter.sync_memory(lkg_snapshot={"k": "v"})


class TestForgeAbstractTools:
    def test_all_tools_have_desc(self) -> None:
        for name, spec in FORGE_ABSTRACT_TOOLS.items():
            assert "desc" in spec, f"{name} missing 'desc'"

    def test_required_tools_present(self) -> None:
        for tool in ("Read", "Write", "Edit", "Bash", "ProposeEvent"):
            assert tool in FORGE_ABSTRACT_TOOLS
