"""Tests for ClaudeSDKAdapter (FR-KA-001..005).

The external dependency ``claude_agent_sdk`` is NOT installed in the test
environment, so it is faked via ``sys.modules`` injection BEFORE importing
the adapter. The fake mirrors EXACTLY the API surface the adapter consumes:

    - ``tool(name, description, input_schema)`` decorator
    - ``create_sdk_mcp_server(name=, version=, tools=)``
    - ``ClaudeAgentOptions(**kwargs)`` (exposes ``.model``)
    - ``ClaudeSDKClient(options=)`` async context manager with
      ``query()`` and ``receive_response()`` (async iterator of messages)
    - message objects identified by ``type(msg).__name__`` —
      ``AssistantMessage`` (``.content`` blocks) and ``ResultMessage``.

All tests are deterministic: no network, no subprocess, no sleeps. The fake
client emits a finite, scripted message sequence so the adapter's internal
driver task always reaches its SENTINEL and terminates.
"""

from __future__ import annotations

import sys
import types
from collections.abc import AsyncIterator
from typing import Any

# ---------------------------------------------------------------------------
# Fake claude_agent_sdk — injected before importing the adapter
# ---------------------------------------------------------------------------


class _FakeOptions:
    """Stand-in for ClaudeAgentOptions. Adapter reads ``.model``."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)
        self.model = kwargs.get("model")


def _fake_tool(name: str, description: str, input_schema: Any):
    """Stand-in for ``@tool`` — returns the function unchanged.

    The adapter only needs the decorated coroutine back so it can hand it to
    ``create_sdk_mcp_server``; it never inspects tool metadata.
    """

    def _decorator(fn: Any) -> Any:
        fn._forge_tool_meta = (name, description, input_schema)
        return fn

    return _decorator


def _fake_create_sdk_mcp_server(*, name: str, version: str, tools: list[Any]) -> Any:
    """Stand-in for ``create_sdk_mcp_server`` — returns an opaque marker."""
    return {"name": name, "version": version, "tools": tools}


# NOTE: the adapter dispatches on ``type(msg).__name__``, so these fakes MUST
# be named exactly ``AssistantMessage`` / ``ResultMessage``.
class AssistantMessage:
    def __init__(self, content: list[Any]) -> None:
        self.content = content


class ResultMessage:
    def __init__(self, subtype: str = "success", result: str | None = None) -> None:
        self.subtype = subtype
        self.result = result
        self.usage = {"input_tokens": 1, "output_tokens": 1}
        self.total_cost_usd = 0.0
        self.duration_ms = 0
        self.session_id = "sess-test"
        self.num_turns = 1


class _TextBlock:
    """Assistant content block with ``.type == 'text'``."""

    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _ThinkingBlock:
    """Assistant content block with ``.type == 'thinking'``."""

    def __init__(self, thinking: str) -> None:
        self.type = "thinking"
        self.thinking = thinking


# Per-test script: the list of messages the next ClaudeSDKClient will emit.
_SCRIPTED_MESSAGES: list[Any] = []


class _FakeSDKClient:
    """Async-context-manager stand-in for ClaudeSDKClient.

    Emits the messages staged in the module-level ``_SCRIPTED_MESSAGES`` list,
    captured at construction time so each spawn gets an independent script.
    """

    def __init__(self, options: Any = None) -> None:
        self.options = options
        self._messages = list(_SCRIPTED_MESSAGES)
        self.queried_with: str | None = None

    async def __aenter__(self) -> _FakeSDKClient:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def query(self, prompt: str) -> None:
        self.queried_with = prompt

    async def receive_response(self) -> AsyncIterator[Any]:
        for msg in self._messages:
            yield msg


def _install_fake_sdk() -> None:
    fake = types.ModuleType("claude_agent_sdk")
    fake.ClaudeAgentOptions = _FakeOptions
    fake.ClaudeSDKClient = _FakeSDKClient
    fake.create_sdk_mcp_server = _fake_create_sdk_mcp_server
    fake.tool = _fake_tool
    sys.modules["claude_agent_sdk"] = fake


_install_fake_sdk()

# Import the adapter AFTER the fake is in place.
from forge_os.adapters.claude_sdk.adapter import (  # noqa: E402
    FORGE_ABSTRACT_TOOLS,
    ClaudeSDKAdapter,
    adapter_id,
)
from forge_os.kernel.types import (  # noqa: E402
    AgentPersona,
    EventKind,
    KernelCapabilities,
    NormalizedEvent,
    ToolResult,
    ToolUseProposal,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_persona(**kwargs: Any) -> AgentPersona:
    defaults = dict(
        name="tester",
        role="test role",
        goal="test goal",
        allowed_tools=["Read", "Write"],
    )
    defaults.update(kwargs)
    return AgentPersona(**defaults)


def _stage_messages(*messages: Any) -> None:
    """Stage the message sequence the next fake client will emit."""
    _SCRIPTED_MESSAGES.clear()
    _SCRIPTED_MESSAGES.extend(messages)


async def _drain(agen: Any, sends: dict[str, ToolResult] | None = None) -> list[NormalizedEvent]:
    """Drain an async generator, auto-sending ToolResults for proposals."""
    events: list[NormalizedEvent] = []
    send_val: ToolResult | None = None
    while True:
        try:
            ev = await agen.asend(send_val)
        except StopAsyncIteration:
            break
        send_val = None
        events.append(ev)
        if isinstance(ev, ToolUseProposal):
            send_val = (sends or {}).get(ev.tool_use_id) or ToolResult(
                tool_use_id=ev.tool_use_id, content="ok"
            )
    return events


# ---------------------------------------------------------------------------
# Capabilities + identity
# ---------------------------------------------------------------------------


class TestGetCapabilities:
    def test_is_kernel_capabilities(self) -> None:
        caps = ClaudeSDKAdapter().get_capabilities()
        assert isinstance(caps, KernelCapabilities)

    def test_kernel_id(self) -> None:
        caps = ClaudeSDKAdapter().get_capabilities()
        assert caps.kernel_id == "claude_sdk"

    def test_client_tools_present(self) -> None:
        caps = ClaudeSDKAdapter().get_capabilities()
        assert "Read" in caps.client_tools
        assert "Write" in caps.client_tools
        assert "ProposeEvent" in caps.client_tools
        assert caps.server_tools == []

    def test_streaming_enabled(self) -> None:
        caps = ClaudeSDKAdapter().get_capabilities()
        assert caps.streaming is True
        assert caps.batch_api is False


class TestAdapterIdentity:
    def test_module_adapter_id(self) -> None:
        assert adapter_id == "claude_sdk"

    def test_abstract_tools_registry(self) -> None:
        for name in ("Read", "Write", "Edit", "Bash", "ProposeEvent"):
            assert name in FORGE_ABSTRACT_TOOLS


# ---------------------------------------------------------------------------
# spawn_agent — happy path
# ---------------------------------------------------------------------------


class TestSpawnAgentHappyPath:
    async def test_text_then_complete(self) -> None:
        _stage_messages(
            AssistantMessage([_TextBlock("hello world")]),
            ResultMessage(subtype="success", result="done"),
        )
        adapter = ClaudeSDKAdapter()
        persona = _make_persona()
        events = await _drain(
            adapter.spawn_agent(persona, "ctx", ["Read"], "agg-1", timeout_s=5.0)
        )

        kinds = [e.kind for e in events]
        assert EventKind.SESSION_STARTED in kinds
        assert EventKind.TEXT_DELTA in kinds
        assert EventKind.AGENT_COMPLETED in kinds

        text_ev = next(e for e in events if e.kind == EventKind.TEXT_DELTA)
        assert text_ev.payload["text"] == "hello world"

    async def test_session_started_first(self) -> None:
        _stage_messages(ResultMessage(subtype="success"))
        adapter = ClaudeSDKAdapter()
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-2", timeout_s=5.0)
        )
        assert events[0].kind == EventKind.SESSION_STARTED
        assert events[0].payload["kernel"] == "claude_sdk"

    async def test_thinking_delta(self) -> None:
        _stage_messages(
            AssistantMessage([_ThinkingBlock("reasoning here")]),
            ResultMessage(subtype="success"),
        )
        adapter = ClaudeSDKAdapter()
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-3", timeout_s=5.0)
        )
        kinds = [e.kind for e in events]
        assert EventKind.THINKING_DELTA in kinds
        think_ev = next(e for e in events if e.kind == EventKind.THINKING_DELTA)
        assert think_ev.payload["text"] == "reasoning here"

    async def test_dict_content_blocks(self) -> None:
        # Adapter also handles dict-shaped blocks (not just attribute objects).
        _stage_messages(
            AssistantMessage([{"type": "text", "text": "from dict"}]),
            ResultMessage(subtype="success"),
        )
        adapter = ClaudeSDKAdapter()
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-4", timeout_s=5.0)
        )
        text_ev = next(e for e in events if e.kind == EventKind.TEXT_DELTA)
        assert text_ev.payload["text"] == "from dict"

    async def test_failure_subtype_maps_to_agent_failed(self) -> None:
        _stage_messages(ResultMessage(subtype="error_max_turns"))
        adapter = ClaudeSDKAdapter()
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-5", timeout_s=5.0)
        )
        kinds = [e.kind for e in events]
        assert EventKind.AGENT_FAILED in kinds


# ---------------------------------------------------------------------------
# spawn_agent — tool-use proposal boundary
# ---------------------------------------------------------------------------


class TestToolUseProposalHandshake:
    async def test_proxy_tool_proposes_and_resumes(self) -> None:
        """Exercise the Proposal boundary via a forge-proxy tool.

        Tool proposals originate from the in-process MCP proxy tools, which the
        real SDK invokes — the fake SDK client never calls tools. So we drive a
        built proxy coroutine directly: it must enqueue a ToolUseProposal, block
        on the matching ToolResult, then return the result content to its caller
        (the SDK). This is the same queue handshake spawn_agent relays.
        """
        import asyncio

        from forge_os.adapters.claude_sdk import adapter as adapter_mod

        events_q: asyncio.Queue = asyncio.Queue()
        results_q: asyncio.Queue = asyncio.Queue()
        server, wire = adapter_mod._build_forge_proxy_server(
            ["Read"], events_q, results_q, "agg-tool", tool_timeout_s=5.0
        )
        # The proxy coroutine is the single tool registered on the server.
        proxy = server["tools"][0]

        async def _run_proxy() -> dict[str, Any]:
            return await proxy({"path": "README.md"})

        proxy_task = asyncio.create_task(_run_proxy())

        # The proxy should enqueue a ToolUseProposal.
        proposal = await asyncio.wait_for(events_q.get(), timeout=5.0)
        assert isinstance(proposal, ToolUseProposal)
        assert proposal.abstract_tool == "Read"
        assert proposal.inputs == {"path": "README.md"}

        # Resume the proxy with a ToolResult.
        await results_q.put(
            ToolResult(tool_use_id=proposal.tool_use_id, content="file body")
        )
        out = await asyncio.wait_for(proxy_task, timeout=5.0)
        assert out["is_error"] is False
        assert out["content"] == [{"type": "text", "text": "file body"}]

    async def test_wire_names_namespaced(self) -> None:
        import asyncio

        from forge_os.adapters.claude_sdk import adapter as adapter_mod

        _server, wire = adapter_mod._build_forge_proxy_server(
            ["Read", "Write"], asyncio.Queue(), asyncio.Queue(), "agg-x"
        )
        assert "mcp__forge-proxy__read" in wire
        assert "mcp__forge-proxy__write" in wire


# ---------------------------------------------------------------------------
# on_event + sync_memory
# ---------------------------------------------------------------------------


class TestOnEvent:
    async def test_no_error(self) -> None:
        adapter = ClaudeSDKAdapter()
        ev = NormalizedEvent(kind=EventKind.SESSION_STARTED, aggregate_id="x")
        await adapter.on_event(ev)  # should not raise


class TestSyncMemory:
    async def test_no_op(self) -> None:
        adapter = ClaudeSDKAdapter()
        await adapter.sync_memory()  # should not raise
        await adapter.sync_memory(lkg_snapshot={"k": "v"})
