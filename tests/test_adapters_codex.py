"""Tests for CodexAdapter (FR-KA-001..005).

The Codex adapter drives a `codex app-server` subprocess over newline-delimited
JSON-RPC 2.0 on stdio. The `codex` binary is NOT installed in CI, so every test
here mocks the subprocess *transport* rather than a missing module:

  * ``shutil.which`` is patched to a fake path so ``_AppServerClient.start``
    proceeds past its PATH check.
  * ``asyncio.create_subprocess_exec`` is patched to return a ``_FakeProcess``
    whose ``stdin`` records outbound JSON-RPC and whose ``stdout`` replays a
    scripted sequence of response/notification lines, then EOFs so the read
    loop terminates (no hangs).

The scripted lines mirror the EXACT app-server message shapes the adapter
parses in ``_translate_stream`` (``item/agentMessage/delta``, ``turn/plan/updated``,
``item/commandExecution/requestApproval``, ``turn/completed``, ...). Outbound
request ids are deterministic (initialize=1, thread/start=2, thread/goal/set=3,
turn/start=4), so responses can be keyed to those ids up front.

Note: the adapter references ``self._drain_stderr`` in ``_AppServerClient.start``
but the method is not defined on the class. To exercise the spawn path at all we
install a harmless async stub for it via monkeypatch (we do not modify the source
under test). This is called out in the test report as a pre-existing source bug.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest

from forge_os.adapters.codex import adapter as codex_mod
from forge_os.adapters.codex.adapter import CodexAdapter, adapter_id
from forge_os.kernel.types import (
    AgentPersona,
    EventKind,
    KernelCapabilities,
    NormalizedEvent,
    ToolResult,
    ToolUseProposal,
)

THREAD_ID = "thread-abc"


# ---------------------------------------------------------------------------
# Fake subprocess transport
# ---------------------------------------------------------------------------


class _FakeStreamWriter:
    """Stand-in for process.stdin: records the JSON-RPC messages written."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    def write(self, data: bytes) -> None:
        for line in data.decode("utf-8").splitlines():
            line = line.strip()
            if line:
                self.messages.append(json.loads(line))

    async def drain(self) -> None:
        return None


class _FakeStreamReader:
    """Stand-in for process.stdout: replays scripted lines then signals EOF.

    ``lines`` are pre-encoded JSON strings (one app-server message each): the
    four handshake *responses* (ids 1-4) followed by per-thread *notifications*
    and *server requests*. After they are exhausted ``readline()`` returns
    ``b""`` (EOF) so the adapter's read loop exits cleanly and no test can hang.

    Pacing matters: the adapter's read loop runs as a concurrent task that
    consumes stdout eagerly. Two causality rules must hold or the adapter hangs:

      1. A *response* line (id 1-4) must not be delivered before the matching
         outbound *request* with that id has been written. If the read loop
         hands back the thread/start response before spawn_agent has issued
         thread/start, ``_dispatch`` finds no pending future and drops it; the
         later real request then waits on a response that will never come.
      2. A *notification* / *server-request* line must not be delivered before
         spawn_agent has registered its per-thread queue (which happens right
         after the id-2 thread/start response). Otherwise ``_dispatch`` routes it
         to the orphan queue and ``sess.inbound.get()`` blocks forever.

    The real app-server satisfies both naturally (it only replies to requests it
    received, and only emits thread events after the thread exists). We reproduce
    that here: response lines (the first ``handshake`` lines, in id order) wait
    for their id to appear among the writer's outbound messages; everything after
    waits for all ``handshake`` ids to have been requested. ``asyncio.sleep(0)``
    yields control so the adapter keeps making progress while we wait.
    """

    def __init__(self, lines: list[str], writer: _FakeStreamWriter, handshake: int) -> None:
        self._lines = [(line + "\n").encode("utf-8") for line in lines]
        self._index = 0
        self._writer = writer
        self._handshake = handshake

    def _requested_ids(self) -> set[int]:
        return {m["id"] for m in self._writer.messages if "id" in m}

    async def readline(self) -> bytes:
        if self._index >= len(self._lines):
            return b""  # EOF
        if self._index < self._handshake:
            # Response line for request id == index + 1.
            needed = self._index + 1
            while needed not in self._requested_ids():
                await asyncio.sleep(0)
        else:
            # Notification / server-request: hold until the handshake completes
            # (so the per-thread queue is registered).
            while not set(range(1, self._handshake + 1)).issubset(self._requested_ids()):
                await asyncio.sleep(0)
        line = self._lines[self._index]
        self._index += 1
        return line


class _FakeProcess:
    """Stand-in for asyncio.subprocess.Process."""

    def __init__(self, stdout_lines: list[str]) -> None:
        self.stdin = _FakeStreamWriter()
        self.stdout = _FakeStreamReader(stdout_lines, self.stdin, handshake=4)
        self.stderr = _FakeStreamReader([], _FakeStreamWriter(), handshake=0)
        self.pid = 4321
        self.returncode: int | None = None

    def terminate(self) -> None:
        self.returncode = 0

    def kill(self) -> None:  # pragma: no cover - defensive
        self.returncode = -9

    async def wait(self) -> int:
        self.returncode = self.returncode if self.returncode is not None else 0
        return self.returncode


def _rpc_response(req_id: int, result: dict) -> str:
    return json.dumps({"id": req_id, "result": result})


def _notification(method: str, params: dict) -> str:
    return json.dumps({"method": method, "params": params})


def _server_request(req_id: int, method: str, params: dict) -> str:
    return json.dumps({"id": req_id, "method": method, "params": params})


# Standard responses to the four requests spawn_agent issues, in id order.
def _handshake_responses() -> list[str]:
    return [
        _rpc_response(1, {}),  # initialize
        _rpc_response(2, {"thread": {"id": THREAD_ID}}),  # thread/start
        _rpc_response(3, {}),  # thread/goal/set
        _rpc_response(4, {"turn": {"id": "turn-1"}}),  # turn/start
    ]


@pytest.fixture
def patched_transport(monkeypatch):
    """Patch the subprocess transport. Returns a setter for stdout lines.

    Usage::

        def test_x(patched_transport):
            proc = patched_transport(["...json line...", ...])
            ...
    """
    monkeypatch.setattr(codex_mod.shutil, "which", lambda _bin: "/usr/bin/codex")

    # The adapter references self._drain_stderr in start() but never defines it.
    # Install a harmless async stub so the spawn path can run under test.
    async def _noop_drain_stderr(self) -> None:
        return None

    monkeypatch.setattr(
        codex_mod._AppServerClient, "_drain_stderr", _noop_drain_stderr, raising=False
    )

    holder: dict[str, _FakeProcess] = {}

    async def _fake_exec(*_args, **_kwargs) -> _FakeProcess:
        return holder["proc"]

    monkeypatch.setattr(codex_mod.asyncio, "create_subprocess_exec", _fake_exec)

    def _set(stdout_lines: list[str]) -> _FakeProcess:
        proc = _FakeProcess(stdout_lines)
        holder["proc"] = proc
        return proc

    return _set


def _make_persona(**kwargs) -> AgentPersona:
    defaults = dict(name="tester", role="test role", goal="test goal",
                    allowed_tools=["Read", "Write", "Bash"])
    defaults.update(kwargs)
    return AgentPersona(**defaults)


async def _drain(
    agen: AsyncIterator[NormalizedEvent],
    sends: dict[str, ToolResult] | None = None,
) -> list[NormalizedEvent]:
    """Drain an async generator, auto-answering proposals with ToolResults."""
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
                tool_use_id=ev.tool_use_id, content="approved"
            )
    return events


# ---------------------------------------------------------------------------
# get_capabilities (FR-KA-001 / FR-KA-002)
# ---------------------------------------------------------------------------


class TestGetCapabilities:
    def test_is_kernel_capabilities(self) -> None:
        assert isinstance(CodexAdapter().get_capabilities(), KernelCapabilities)

    def test_kernel_id_is_codex(self) -> None:
        assert CodexAdapter().get_capabilities().kernel_id == "codex"

    def test_streaming_and_thinking(self) -> None:
        caps = CodexAdapter().get_capabilities()
        assert caps.streaming is True
        assert caps.extended_thinking is True
        assert caps.deterministic_output is False

    def test_mcp_and_tools(self) -> None:
        caps = CodexAdapter().get_capabilities()
        assert caps.mcp_remote is True
        assert caps.mcp_local_stdio is True
        assert "Bash" in caps.client_tools
        assert "web_search" in caps.server_tools

    def test_notes_describe_native_approval(self) -> None:
        caps = CodexAdapter().get_capabilities()
        assert "native_approval_boundary" in caps.notes


class TestAdapterId:
    def test_module_adapter_id(self) -> None:
        assert adapter_id == "codex"

    def test_matches_capabilities_kernel_id(self) -> None:
        assert CodexAdapter().get_capabilities().kernel_id == adapter_id


class TestConstruction:
    def test_invalid_execution_boundary_raises(self) -> None:
        with pytest.raises(ValueError):
            CodexAdapter(execution_boundary="bogus")

    def test_valid_boundaries(self) -> None:
        assert CodexAdapter(execution_boundary="kernel") is not None
        assert CodexAdapter(execution_boundary="forge") is not None


# ---------------------------------------------------------------------------
# spawn_agent — happy path
# ---------------------------------------------------------------------------


class TestSpawnAgentHappyPath:
    async def test_session_text_completed(self, patched_transport) -> None:
        patched_transport(
            _handshake_responses()
            + [
                _notification(
                    "item/agentMessage/delta",
                    {"threadId": THREAD_ID, "delta": "Hello "},
                ),
                _notification(
                    "item/agentMessage/delta",
                    {"threadId": THREAD_ID, "delta": "world"},
                ),
                _notification(
                    "turn/completed",
                    {"threadId": THREAD_ID, "turn": {"status": "completed"}},
                ),
            ]
        )
        adapter = CodexAdapter()
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-1")
        )

        kinds = [e.kind for e in events]
        assert kinds[0] == EventKind.SESSION_STARTED
        assert EventKind.TEXT_DELTA in kinds
        assert kinds[-1] == EventKind.AGENT_COMPLETED

        texts = [e.payload["text"] for e in events if e.kind == EventKind.TEXT_DELTA]
        assert texts == ["Hello ", "world"]

        await adapter._client.close()

    async def test_session_started_payload(self, patched_transport) -> None:
        patched_transport(
            _handshake_responses()
            + [
                _notification(
                    "turn/completed",
                    {"threadId": THREAD_ID, "turn": {"status": "completed"}},
                ),
            ]
        )
        adapter = CodexAdapter()
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-2")
        )

        started = next(e for e in events if e.kind == EventKind.SESSION_STARTED)
        assert started.payload["thread_id"] == THREAD_ID
        assert started.payload["kernel"] == "codex"

        await adapter._client.close()

    async def test_thinking_plan_and_diff(self, patched_transport) -> None:
        patched_transport(
            _handshake_responses()
            + [
                _notification(
                    "item/reasoning/textDelta",
                    {"threadId": THREAD_ID, "delta": "thinking..."},
                ),
                _notification(
                    "turn/plan/updated",
                    {"threadId": THREAD_ID, "plan": ["step 1"], "explanation": "why"},
                ),
                _notification(
                    "turn/diff/updated",
                    {"threadId": THREAD_ID, "diff": "--- a\n+++ b"},
                ),
                _notification(
                    "turn/completed",
                    {"threadId": THREAD_ID, "turn": {"status": "completed"}},
                ),
            ]
        )
        adapter = CodexAdapter()
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-3")
        )

        kinds = [e.kind for e in events]
        assert EventKind.THINKING_DELTA in kinds
        assert EventKind.PLAN_UPDATED in kinds
        assert EventKind.DIFF_UPDATED in kinds

        plan = next(e for e in events if e.kind == EventKind.PLAN_UPDATED)
        assert plan.payload["plan"] == ["step 1"]

        await adapter._client.close()

    async def test_websearch_server_tool(self, patched_transport) -> None:
        patched_transport(
            _handshake_responses()
            + [
                _notification(
                    "item/completed",
                    {
                        "threadId": THREAD_ID,
                        "item": {"type": "webSearch", "query": "forge os"},
                    },
                ),
                _notification(
                    "turn/completed",
                    {"threadId": THREAD_ID, "turn": {"status": "completed"}},
                ),
            ]
        )
        adapter = CodexAdapter()
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-4")
        )

        server_evs = [
            e for e in events if e.kind == EventKind.SERVER_TOOL_EXECUTED
        ]
        assert len(server_evs) == 1
        assert server_evs[0].payload["tool"] == "web_search"
        assert server_evs[0].payload["execution"] == "kernel_executed"

        await adapter._client.close()


# ---------------------------------------------------------------------------
# spawn_agent — failure / abort
# ---------------------------------------------------------------------------


class TestSpawnAgentFailure:
    async def test_turn_failed_emits_agent_failed(self, patched_transport) -> None:
        patched_transport(
            _handshake_responses()
            + [
                _notification(
                    "turn/completed",
                    {
                        "threadId": THREAD_ID,
                        "turn": {"status": "failed", "error": "boom"},
                    },
                ),
            ]
        )
        adapter = CodexAdapter()
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-5")
        )

        kinds = [e.kind for e in events]
        assert kinds[-1] == EventKind.AGENT_FAILED
        failed = next(e for e in events if e.kind == EventKind.AGENT_FAILED)
        assert failed.payload["error"] == "boom"

        await adapter._client.close()

    async def test_error_notification_emits_agent_failed(
        self, patched_transport
    ) -> None:
        patched_transport(
            _handshake_responses()
            + [
                _notification(
                    "error",
                    {"threadId": THREAD_ID, "error": "fatal"},
                ),
            ]
        )
        adapter = CodexAdapter()
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Read"], "agg-6")
        )

        failed = next(e for e in events if e.kind == EventKind.AGENT_FAILED)
        assert failed.payload["error"] == "fatal"

        await adapter._client.close()


# ---------------------------------------------------------------------------
# spawn_agent — approval / proposal handshake
# ---------------------------------------------------------------------------


class TestProposalHandshake:
    async def test_command_approval_proposed_and_accepted(
        self, patched_transport
    ) -> None:
        proc = patched_transport(
            _handshake_responses()
            + [
                _server_request(
                    10,
                    "item/commandExecution/requestApproval",
                    {
                        "threadId": THREAD_ID,
                        "itemId": "item-1",
                        "reason": "needs to run ls",
                        "command": "ls -la",
                        "cwd": "/tmp",
                    },
                ),
                _notification(
                    "turn/completed",
                    {"threadId": THREAD_ID, "turn": {"status": "completed"}},
                ),
            ]
        )
        adapter = CodexAdapter()
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Bash"], "agg-7")
        )

        proposals = [e for e in events if isinstance(e, ToolUseProposal)]
        assert len(proposals) == 1
        prop = proposals[0]
        assert prop.kind == EventKind.TOOL_USE_PROPOSED
        assert prop.abstract_tool == "Bash"
        assert prop.tool_name == "shell"
        assert prop.inputs["command"] == "ls -la"

        assert EventKind.AGENT_COMPLETED in [e.kind for e in events]

        # The adapter must have answered the server request (id 10) with accept.
        decisions = [
            m for m in proc.stdin.messages
            if m.get("id") == 10 and "result" in m
        ]
        assert len(decisions) == 1
        assert decisions[0]["result"] == {"decision": "accept"}

        await adapter._client.close()

    async def test_file_change_approval_maps_to_write(
        self, patched_transport
    ) -> None:
        patched_transport(
            _handshake_responses()
            + [
                _server_request(
                    11,
                    "item/fileChange/requestApproval",
                    {
                        "threadId": THREAD_ID,
                        "itemId": "item-2",
                        "changes": [{"kind": "add", "path": "new.py"}],
                    },
                ),
                _notification(
                    "turn/completed",
                    {"threadId": THREAD_ID, "turn": {"status": "completed"}},
                ),
            ]
        )
        adapter = CodexAdapter()
        events = await _drain(
            adapter.spawn_agent(_make_persona(), "ctx", ["Write"], "agg-8")
        )

        prop = next(e for e in events if isinstance(e, ToolUseProposal))
        assert prop.abstract_tool == "Write"
        assert prop.tool_name == "apply_patch"

        await adapter._client.close()

    async def test_declined_proposal_sends_decline(
        self, patched_transport
    ) -> None:
        proc = patched_transport(
            _handshake_responses()
            + [
                _server_request(
                    12,
                    "item/commandExecution/requestApproval",
                    {
                        "threadId": THREAD_ID,
                        "itemId": "item-3",
                        "command": "rm -rf /",
                    },
                ),
                _notification(
                    "turn/completed",
                    {"threadId": THREAD_ID, "turn": {"status": "completed"}},
                ),
            ]
        )
        adapter = CodexAdapter()

        async def _drain_declining() -> list[NormalizedEvent]:
            events: list[NormalizedEvent] = []
            send_val: ToolResult | None = None
            agen = adapter.spawn_agent(_make_persona(), "ctx", ["Bash"], "agg-9")
            while True:
                try:
                    ev = await agen.asend(send_val)
                except StopAsyncIteration:
                    break
                send_val = None
                events.append(ev)
                if isinstance(ev, ToolUseProposal):
                    send_val = ToolResult(
                        tool_use_id=ev.tool_use_id,
                        content="policy violation",
                        is_error=True,
                    )
            return events

        await _drain_declining()

        decisions = [
            m for m in proc.stdin.messages
            if m.get("id") == 12 and "result" in m
        ]
        assert decisions[0]["result"] == {"decision": "decline"}

        await adapter._client.close()


# ---------------------------------------------------------------------------
# on_event / sync_memory
# ---------------------------------------------------------------------------


class TestSyncMemory:
    async def test_no_op(self) -> None:
        adapter = CodexAdapter()
        assert await adapter.sync_memory() is None
        assert await adapter.sync_memory(lkg_snapshot={"k": "v"}) is None
