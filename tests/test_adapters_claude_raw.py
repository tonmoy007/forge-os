"""Tests for ClaudeRawAdapter (FR-KA-001..005).

The ``anthropic`` package is NOT installed in the test environment. The
adapter has a module-level guarded import that raises ImportError without it,
so we inject a fake ``anthropic`` module into ``sys.modules`` BEFORE importing
the adapter. The fake mirrors only the surface the adapter actually consumes:

    - anthropic.AsyncAnthropic(api_key=..., max_retries=...) -> .messages
    - client.messages.stream(**kwargs)  (async context manager)
        - ``async for ev in stream`` yielding event objects
        - ``await stream.get_final_message()`` -> final message
    - anthropic.APIError  (Exception subclass)

No real network, no sleeps; the fake stream replays scripted events.
"""

from __future__ import annotations

import sys
import types as _types
from collections.abc import AsyncIterator
from typing import Any

# ---------------------------------------------------------------------------
# Fake ``anthropic`` module — must be installed before importing the adapter.
# ---------------------------------------------------------------------------


class _FakeAPIError(Exception):
    """Stand-in for anthropic.APIError."""


class _FakeStream:
    """Async-context-manager stream replaying scripted events.

    Mirrors the adapter's usage in ``_run_one_turn``: it is entered via
    ``async with``, iterated with ``async for``, then ``get_final_message()``
    is awaited. A configured ``raise_on`` simulates an API error.
    """

    def __init__(
        self,
        events: list[Any],
        final_message: Any,
        raise_on: Exception | None = None,
    ) -> None:
        self._events = events
        self._final_message = final_message
        self._raise_on = raise_on

    async def __aenter__(self) -> _FakeStream:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def __aiter__(self) -> AsyncIterator[Any]:
        if self._raise_on is not None:
            raise self._raise_on
        for ev in self._events:
            yield ev

    async def get_final_message(self) -> Any:
        return self._final_message


class _FakeMessages:
    """Holds a per-call stream factory configured by each test."""

    def __init__(self) -> None:
        self._stream_factory = None

    def stream(self, **kwargs: Any) -> _FakeStream:
        if self._stream_factory is None:
            raise AssertionError("no stream factory configured for this test")
        return self._stream_factory(kwargs)


class _FakeAsyncAnthropic:
    """Stand-in for anthropic.AsyncAnthropic."""

    def __init__(self, *, api_key: str | None = None, max_retries: int = 3) -> None:
        self.api_key = api_key
        self.max_retries = max_retries
        self.messages = _FakeMessages()


_fake_anthropic = _types.ModuleType("anthropic")
_fake_anthropic.AsyncAnthropic = _FakeAsyncAnthropic  # type: ignore[attr-defined]
_fake_anthropic.APIError = _FakeAPIError  # type: ignore[attr-defined]
sys.modules["anthropic"] = _fake_anthropic

# Import the adapter only AFTER the fake module is registered.
from forge_os.adapters.claude_raw.adapter import (  # noqa: E402
    ANTHROPIC_CLIENT_TOOLS,
    ClaudeRawAdapter,
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
# Lightweight stand-ins for Anthropic stream event / message objects.
# ---------------------------------------------------------------------------


class _Delta:
    def __init__(self, dtype: str, **fields: Any) -> None:
        self.type = dtype
        for key, value in fields.items():
            setattr(self, key, value)


class _StreamEvent:
    def __init__(self, etype: str, delta: _Delta | None = None) -> None:
        self.type = etype
        self.delta = delta


def _text_delta_event(text: str) -> _StreamEvent:
    return _StreamEvent("content_block_delta", _Delta("text_delta", text=text))


class _Usage:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def model_dump(self) -> dict[str, Any]:
        return dict(self._data)


class _FinalMessage:
    """Mirrors the fields the adapter reads off the final message."""

    def __init__(
        self,
        stop_reason: str,
        content: list[Any] | None = None,
        usage: _Usage | None = None,
    ) -> None:
        self.stop_reason = stop_reason
        self.content = content or []
        self.usage = usage


def _make_persona(**kwargs: Any) -> AgentPersona:
    defaults = dict(
        name="tester",
        role="test role",
        goal="test goal",
        allowed_tools=[],
        allowed_server_tools=[],
    )
    defaults.update(kwargs)
    return AgentPersona(**defaults)


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
        if isinstance(ev, ToolUseProposal) and sends is not None:
            send_val = sends.get(ev.tool_use_id) or ToolResult(
                tool_use_id=ev.tool_use_id, content="ok"
            )
    return events


def _configure_stream(
    adapter: ClaudeRawAdapter,
    *,
    events: list[Any] | None = None,
    final_message: Any = None,
    raise_on: Exception | None = None,
) -> None:
    """Wire the adapter's fake client to return a configured stream."""
    fake_messages = adapter._client.messages  # type: ignore[attr-defined]

    def _factory(_kwargs: dict[str, Any]) -> _FakeStream:
        return _FakeStream(events or [], final_message, raise_on=raise_on)

    fake_messages._stream_factory = _factory


# ---------------------------------------------------------------------------
# get_capabilities()
# ---------------------------------------------------------------------------


class TestGetCapabilities:
    def test_kernel_id(self) -> None:
        caps = ClaudeRawAdapter().get_capabilities()
        assert caps.kernel_id == "claude_raw"

    def test_is_kernel_capabilities(self) -> None:
        assert isinstance(ClaudeRawAdapter().get_capabilities(), KernelCapabilities)

    def test_client_tools_non_empty(self) -> None:
        caps = ClaudeRawAdapter().get_capabilities()
        assert caps.client_tools
        for tool in ANTHROPIC_CLIENT_TOOLS:
            assert tool in caps.client_tools

    def test_server_tools_present(self) -> None:
        caps = ClaudeRawAdapter().get_capabilities()
        assert "WebSearch" in caps.server_tools

    def test_streaming_enabled(self) -> None:
        caps = ClaudeRawAdapter().get_capabilities()
        assert caps.streaming is True


class TestAdapterId:
    def test_module_adapter_id(self) -> None:
        assert adapter_id == "claude_raw"


# ---------------------------------------------------------------------------
# spawn_agent() — happy path
# ---------------------------------------------------------------------------


class TestSpawnAgentHappyPath:
    async def test_text_then_complete(self) -> None:
        adapter = ClaudeRawAdapter()
        final = _FinalMessage(
            stop_reason="end_turn",
            content=[],
            usage=_Usage({"input_tokens": 10, "output_tokens": 5}),
        )
        _configure_stream(
            adapter,
            events=[_text_delta_event("hello "), _text_delta_event("world")],
            final_message=final,
        )

        persona = _make_persona()
        events = await _drain(
            adapter.spawn_agent(persona, "ctx", [], "agg-1")
        )

        kinds = [e.kind for e in events]
        assert EventKind.SESSION_STARTED in kinds
        assert EventKind.TEXT_DELTA in kinds
        assert EventKind.AGENT_COMPLETED in kinds

        text_evs = [e for e in events if e.kind == EventKind.TEXT_DELTA]
        assert [e.payload["text"] for e in text_evs] == ["hello ", "world"]

        completed = next(e for e in events if e.kind == EventKind.AGENT_COMPLETED)
        assert completed.payload["stop_reason"] == "end_turn"
        assert completed.payload["usage"] == {"input_tokens": 10, "output_tokens": 5}

    async def test_session_started_first(self) -> None:
        adapter = ClaudeRawAdapter()
        final = _FinalMessage(stop_reason="end_turn")
        _configure_stream(adapter, events=[], final_message=final)

        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", [], "agg-2")
        )
        assert events[0].kind == EventKind.SESSION_STARTED
        assert events[0].payload["persona"] == "tester"


# ---------------------------------------------------------------------------
# spawn_agent() — error path
# ---------------------------------------------------------------------------


class TestSpawnAgentErrorPath:
    async def test_api_error_yields_failed(self) -> None:
        adapter = ClaudeRawAdapter()
        _configure_stream(
            adapter,
            events=[],
            final_message=_FinalMessage(stop_reason="end_turn"),
            raise_on=_FakeAPIError("boom"),
        )

        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", [], "agg-3")
        )

        kinds = [e.kind for e in events]
        assert EventKind.AGENT_FAILED in kinds
        failed = next(e for e in events if e.kind == EventKind.AGENT_FAILED)
        assert failed.payload["reason"] == "api_error"
        assert "boom" in failed.payload["detail"]

    async def test_unexpected_error_yields_failed(self) -> None:
        adapter = ClaudeRawAdapter()
        _configure_stream(
            adapter,
            events=[],
            final_message=_FinalMessage(stop_reason="end_turn"),
            raise_on=ValueError("kaboom"),
        )

        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", [], "agg-4")
        )
        failed = next(e for e in events if e.kind == EventKind.AGENT_FAILED)
        assert failed.payload["reason"] == "internal_error"


# ---------------------------------------------------------------------------
# sync_memory() / on_event()
# ---------------------------------------------------------------------------


class TestSyncMemory:
    async def test_no_op(self) -> None:
        adapter = ClaudeRawAdapter()
        await adapter.sync_memory()  # should not raise
        await adapter.sync_memory(lkg_snapshot={"k": "v"})


class TestOnEvent:
    async def test_no_error(self) -> None:
        adapter = ClaudeRawAdapter()
        ev = NormalizedEvent(kind=EventKind.SESSION_STARTED, aggregate_id="x")
        await adapter.on_event(ev)  # should not raise
