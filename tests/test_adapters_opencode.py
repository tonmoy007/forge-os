"""Tests for OpenCodeAdapter (FR-KA-001..005).

OpenCode talks to an `opencode serve` instance over HTTP + SSE via the
`opencode-ai` SDK. Neither the SDK nor a live server are available in the test
environment, so the SDK is stubbed and the client is replaced with a fake whose
`event.list()` yields scripted SSE-shaped events. No real network occurs.

The fake event objects mirror the exact OpenCode event shapes the adapter
parses in `_consume_sse`: `type` + `properties` with the field names the source
reads (`message.part.delta` → part.text/thinking, `permission.requested`,
`tool.execute.after`, `session.idle`, `session.error`).
"""

from __future__ import annotations

import sys
import types as _types
from typing import Any

# ---------------------------------------------------------------------------
# Stub the `opencode_ai` SDK before importing the adapter so the guarded import
# in adapter.py resolves and `_SDK_AVAILABLE` can be flipped on. The real SDK is
# not installed; the adapter only needs the two symbols it imports by name.
# ---------------------------------------------------------------------------

if "opencode_ai" not in sys.modules:
    _fake_sdk = _types.ModuleType("opencode_ai")

    class _FakeAPIError(Exception):
        """Stand-in for opencode_ai.APIError."""

    class _FakeAsyncOpencode:
        """Stand-in for opencode_ai.AsyncOpencode (never instantiated in tests)."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.base_url = kwargs.get("base_url")

    _fake_sdk.APIError = _FakeAPIError
    _fake_sdk.AsyncOpencode = _FakeAsyncOpencode
    sys.modules["opencode_ai"] = _fake_sdk

from forge_os.adapters.opencode import adapter as opencode_adapter  # noqa: E402
from forge_os.adapters.opencode.adapter import (  # noqa: E402
    OPENCODE_BUILTIN_TOOLS,
    OpenCodeAdapter,
    OpenCodeAgentPersona,
    adapter_id,
    build_session_permissions,
)
from forge_os.kernel.types import (  # noqa: E402
    EventKind,
    KernelCapabilities,
    NormalizedEvent,
    ToolResult,
    ToolUseProposal,
)

# Ensure the module-level SDK flag is on regardless of import-time availability.
opencode_adapter._SDK_AVAILABLE = True
opencode_adapter.AsyncOpencode = sys.modules["opencode_ai"].AsyncOpencode


# ---------------------------------------------------------------------------
# Fakes for the SDK client surface the adapter calls.
# ---------------------------------------------------------------------------

class _Model:
    """Minimal pydantic-like object exposing model_dump()."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def model_dump(self) -> dict[str, Any]:
        return dict(self._data)


class _FakeEventStream:
    """Async-iterable returned by client.event.list() — yields scripted events."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = [_Model(e) for e in events]

    def __aiter__(self) -> _FakeEventStream:
        self._it = iter(self._events)
        return self

    async def __anext__(self) -> _Model:
        try:
            return next(self._it)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _FakeEventNamespace:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events

    async def list(self) -> _FakeEventStream:
        return _FakeEventStream(self._events)


class _FakePermissionNamespace:
    def __init__(self) -> None:
        self.responses: list[dict[str, Any]] = []

    async def respond(self, **kwargs: Any) -> None:
        self.responses.append(kwargs)


class _FakeSessionNamespace:
    def __init__(self, session_id: str = "sess-1") -> None:
        self._session_id = session_id
        self.permission = _FakePermissionNamespace()
        self.created: list[dict[str, Any]] = []
        self.prompts: list[dict[str, Any]] = []

    async def create(self, **body: Any) -> _Model:
        self.created.append(body)
        return _Model({"id": self._session_id})

    async def prompt(self, **kwargs: Any) -> None:
        self.prompts.append(kwargs)


class _FakeClient:
    """Replaces AsyncOpencode. Drives spawn_agent without any network."""

    def __init__(
        self,
        events: list[dict[str, Any]],
        session_id: str = "sess-1",
    ) -> None:
        self.event = _FakeEventNamespace(events)
        self.session = _FakeSessionNamespace(session_id)
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _make_persona(**kwargs: Any) -> OpenCodeAgentPersona:
    defaults = dict(
        name="tester",
        role="test role",
        goal="test goal",
        allowed_tools=["Read", "Write"],
    )
    defaults.update(kwargs)
    return OpenCodeAgentPersona(**defaults)


def _adapter_with_events(
    events: list[dict[str, Any]],
    session_id: str = "sess-1",
) -> OpenCodeAdapter:
    """Build an adapter with a fake client injected (no __aenter__/network)."""
    adapter = OpenCodeAdapter(auto_spawn_server=False)
    adapter._client = _FakeClient(events, session_id)
    return adapter


async def _drain(
    agen: Any,
    result_content: str = "ok",
) -> list[NormalizedEvent]:
    """Drain spawn_agent, auto-answering any ToolUseProposal with a ToolResult."""
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
            send_val = ToolResult(
                tool_use_id=ev.tool_use_id, content=result_content
            )
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetCapabilities:
    def test_kernel_id(self) -> None:
        caps = _adapter_with_events([]).get_capabilities()
        assert caps.kernel_id == "opencode"

    def test_is_kernel_capabilities(self) -> None:
        caps = _adapter_with_events([]).get_capabilities()
        assert isinstance(caps, KernelCapabilities)

    def test_client_tools_present(self) -> None:
        caps = _adapter_with_events([]).get_capabilities()
        assert "Read" in caps.client_tools
        assert "Write" in caps.client_tools
        assert caps.client_tools == list(OPENCODE_BUILTIN_TOOLS.keys())

    def test_streaming_and_server_tools(self) -> None:
        caps = _adapter_with_events([]).get_capabilities()
        assert caps.streaming is True
        assert caps.server_tools == []


class TestAdapterId:
    def test_module_level_adapter_id(self) -> None:
        assert adapter_id == "opencode"

    def test_class_kernel_id(self) -> None:
        assert OpenCodeAdapter.KERNEL_ID == "opencode"


class TestConstruction:
    def test_requires_sdk(self) -> None:
        # When the SDK is reported absent, __init__ must fail loudly.
        original = opencode_adapter._SDK_AVAILABLE
        opencode_adapter._SDK_AVAILABLE = False
        try:
            import pytest

            with pytest.raises(RuntimeError, match="opencode-ai SDK not installed"):
                OpenCodeAdapter(auto_spawn_server=False)
        finally:
            opencode_adapter._SDK_AVAILABLE = original

    async def test_spawn_without_client_raises(self) -> None:
        import pytest

        adapter = OpenCodeAdapter(auto_spawn_server=False)
        # No client injected → spawn_agent must refuse before any yield.
        agen = adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-x")
        with pytest.raises(RuntimeError, match="outside `async with`"):
            await agen.asend(None)


class TestSpawnAgentHappyPath:
    async def test_session_then_text_then_complete(self) -> None:
        events_script = [
            {"type": "server.connected", "properties": {}},
            {
                "type": "message.part.delta",
                "properties": {
                    "session_id": "sess-1",
                    "part": {"text": "Hello "},
                },
            },
            {
                "type": "message.part.delta",
                "properties": {
                    "session_id": "sess-1",
                    "part": {"text": "world"},
                },
            },
            {"type": "session.idle", "properties": {"session_id": "sess-1"}},
        ]
        adapter = _adapter_with_events(events_script)
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-1")
        )

        kinds = [e.kind for e in events]
        assert EventKind.SESSION_STARTED in kinds
        assert EventKind.TEXT_DELTA in kinds
        assert EventKind.AGENT_COMPLETED in kinds

        texts = [e.payload["text"] for e in events if e.kind == EventKind.TEXT_DELTA]
        assert texts == ["Hello ", "world"]

    async def test_session_started_payload(self) -> None:
        adapter = _adapter_with_events(
            [{"type": "session.idle", "properties": {"session_id": "sess-1"}}]
        )
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-2")
        )
        started = next(e for e in events if e.kind == EventKind.SESSION_STARTED)
        assert started.payload["session_id"] == "sess-1"
        assert started.payload["kernel"] == "opencode"

    async def test_thinking_delta(self) -> None:
        adapter = _adapter_with_events([
            {
                "type": "message.part.delta",
                "properties": {
                    "session_id": "sess-1",
                    "part": {"thinking": "reasoning..."},
                },
            },
            {"type": "session.idle", "properties": {"session_id": "sess-1"}},
        ])
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-3")
        )
        kinds = [e.kind for e in events]
        assert EventKind.THINKING_DELTA in kinds
        thinking = next(e for e in events if e.kind == EventKind.THINKING_DELTA)
        assert thinking.payload["thinking"] == "reasoning..."

    async def test_tool_execute_after_audit_event(self) -> None:
        adapter = _adapter_with_events([
            {
                "type": "tool.execute.after",
                "properties": {
                    "session_id": "sess-1",
                    "tool": "read",
                    "duration_ms": 12,
                    "ok": True,
                },
            },
            {"type": "session.idle", "properties": {"session_id": "sess-1"}},
        ])
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-4")
        )
        audit = next(
            e for e in events if e.kind == EventKind.SERVER_TOOL_EXECUTED
        )
        assert audit.payload["tool"] == "read"
        assert audit.payload["ok"] is True


class TestSpawnAgentErrorPath:
    async def test_session_error_yields_failed(self) -> None:
        adapter = _adapter_with_events([
            {
                "type": "session.error",
                "properties": {"session_id": "sess-1", "message": "boom"},
            },
        ])
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-5")
        )
        kinds = [e.kind for e in events]
        assert EventKind.AGENT_FAILED in kinds
        failed = next(e for e in events if e.kind == EventKind.AGENT_FAILED)
        assert failed.payload["reason"] == "session_error"


class TestToolUseProposal:
    async def test_permission_request_yields_proposal_and_responds(self) -> None:
        adapter = _adapter_with_events([
            {
                "type": "permission.requested",
                "properties": {
                    "session_id": "sess-1",
                    "permission_id": "perm-1",
                    "tool": "read",
                    "inputs": {"path": "/tmp/x"},
                },
            },
            {"type": "session.idle", "properties": {"session_id": "sess-1"}},
        ])
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-6"),
            result_content="file body",
        )

        kinds = [e.kind for e in events]
        assert EventKind.TOOL_USE_PROPOSED in kinds
        assert EventKind.AGENT_COMPLETED in kinds

        proposal = next(e for e in events if isinstance(e, ToolUseProposal))
        assert proposal.tool_use_id == "perm-1"
        assert proposal.tool_name == "read"
        assert proposal.abstract_tool == "Read"  # wire→abstract reverse lookup
        assert proposal.inputs == {"path": "/tmp/x"}

        # The ToolResult must have been forwarded to the permission API as allow.
        responses = adapter._client.session.permission.responses
        assert len(responses) == 1
        assert responses[0]["permission_id"] == "perm-1"
        assert responses[0]["decision"] == "allow"
        assert responses[0]["response_data"] == "file body"

    async def test_denied_tool_result_sends_deny(self) -> None:
        adapter = _adapter_with_events([
            {
                "type": "permission.requested",
                "properties": {
                    "session_id": "sess-1",
                    "permission_id": "perm-9",
                    "tool": "bash",
                    "inputs": {},
                },
            },
            {"type": "session.idle", "properties": {"session_id": "sess-1"}},
        ])

        agen = adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-7")
        send_val: ToolResult | None = None
        while True:
            try:
                ev = await agen.asend(send_val)
            except StopAsyncIteration:
                break
            send_val = None
            if isinstance(ev, ToolUseProposal):
                send_val = ToolResult(
                    tool_use_id=ev.tool_use_id,
                    content="not allowed",
                    is_error=True,
                )

        responses = adapter._client.session.permission.responses
        assert responses[0]["decision"] == "deny"
        assert "response_data" not in responses[0]


class TestBuildSessionPermissions:
    def test_default_deny_then_ask(self) -> None:
        permissions, allowlist = build_session_permissions(["Read"])
        # Every known builtin defaults to deny...
        assert permissions["write"] == "deny"
        # ...except the allowed one, flipped to ask.
        assert permissions["read"] == "ask"
        assert allowlist == ["read"]

    def test_unknown_tool_skipped(self) -> None:
        permissions, allowlist = build_session_permissions(["Nonexistent"])
        assert "Nonexistent" not in allowlist
        assert all(v == "deny" for v in permissions.values())


class TestOnEvent:
    async def test_no_error(self) -> None:
        adapter = _adapter_with_events([])
        ev = NormalizedEvent(kind=EventKind.SESSION_STARTED, aggregate_id="x")
        await adapter.on_event(ev)  # should not raise


class TestSyncMemory:
    async def test_no_op(self) -> None:
        adapter = _adapter_with_events([])
        await adapter.sync_memory()  # should not raise
        await adapter.sync_memory(lkg_snapshot={"k": "v"})
