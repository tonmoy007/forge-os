"""Tests for OpenClawAdapter (Phase 11 S3 — FR-OCA-001..006).

No concrete OpenClaw Gateway exists, so the transport is a fake ACP client whose
``prompt()`` yields scripted ``session/update`` params. No network occurs. The
adapter's translation, tool policy, webhook bridge, memory-safety guard, and
offline fallback are all exercised directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from forge_os.adapters.openclaw import (
    FORGE_PROTECTED_FILES,
    OPENCLAW_TOOL_MAP,
    OpenClawAdapter,
    OpenClawChannelAdapter,
    OpenClawError,
    adapter_id,
    bridge_webhook,
    build_openclaw_session_config,
    canonical_relpath,
    is_protected_path,
    map_tool_policy,
    sync_insights_back,
    wire_to_abstract,
)
from forge_os.adapters.registry import (
    AdapterRegistryError,
    PlaceholderAdapter,
    get_adapter_registry,
)
from forge_os.kernel.acp_client import ACPClientError, SessionInfo
from forge_os.kernel.types import (
    AgentPersona,
    EventKind,
    KernelCapabilities,
    NormalizedEvent,
    ToolResult,
    ToolUseProposal,
)
from forge_os.schemas.openclaw import (
    OpenClawSessionConfig,
    OpenClawWebhook,
    OpenClawWebhookKind,
)
from forge_os.schemas.security import SecurityDecision

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeACPClient:
    """Stand-in for ACPClient — yields scripted ACP session/update params."""

    def __init__(
        self,
        updates: list[dict[str, Any]],
        session_id: str = "oc-sess-1",
        sessions: list[SessionInfo] | None = None,
    ) -> None:
        self._updates = updates
        self.session_id = session_id
        self._sessions = sessions or []
        self.started = False
        self.resumed: list[str] = []
        self.closed: list[str] = []

    def start(self) -> dict[str, Any]:
        self.started = True
        return {}

    def prompt(self, prompt_text: str, session_id: str | None = None):
        yield from self._updates
        return {"final": True}

    def session_list(self) -> list[SessionInfo]:
        return self._sessions

    def session_resume(self, session_id: str) -> None:
        self.resumed.append(session_id)

    def session_close(self, session_id: str) -> None:
        self.closed.append(session_id)


class _AllowEnforcer:
    def validate_action(self, actor, action, target=None, capability=None):  # noqa: ANN001
        return SecurityDecision.ALLOWED


class _DenyEnforcer:
    def validate_action(self, actor, action, target=None, capability=None):  # noqa: ANN001
        return SecurityDecision.DENIED


class _WarnEnforcer:
    def validate_action(self, actor, action, target=None, capability=None):  # noqa: ANN001
        return SecurityDecision.WARNED


class _FailingStartClient:
    """ACPClient stand-in whose start() fails after a process would have spawned."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.stopped = False

    def start(self) -> dict[str, Any]:
        raise ACPClientError("init failed")

    def stop(self) -> None:
        self.stopped = True


def _persona(**kwargs: Any) -> AgentPersona:
    defaults = dict(
        name="tester",
        role="test role",
        goal="test goal",
        allowed_tools=["Read", "Write"],
    )
    defaults.update(kwargs)
    return AgentPersona(**defaults)


async def _drain(agen: Any, result_content: str = "ok") -> list[NormalizedEvent]:
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
            send_val = ToolResult(tool_use_id=ev.tool_use_id, content=result_content)
    return events


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_session_config_roundtrip(self) -> None:
        sc = OpenClawSessionConfig(
            agent_name="a", soul_md="s", identity_md="i", system_prompt="p"
        )
        assert sc.model == "claude-opus-4-7"
        assert sc.allowed_tools == []

    def test_webhook_kind_enum(self) -> None:
        wh = OpenClawWebhook(event="agent.stopped", session_id="s1")
        assert wh.event == OpenClawWebhookKind.AGENT_STOPPED


# ---------------------------------------------------------------------------
# FR-OCA-001 — persona translation
# ---------------------------------------------------------------------------

class TestBuildSessionConfig:
    def test_projects_persona_onto_soul_identity_prompt(self) -> None:
        persona = _persona(
            constraints=["no prose"], preferred_model="claude-x", max_tokens=2048
        )
        sc = build_openclaw_session_config(persona, ["read_file"])
        assert sc.agent_name == "tester"
        assert "tester" in sc.soul_md
        assert "test goal" in sc.identity_md
        assert "no prose" in sc.system_prompt
        assert sc.model == "claude-x"
        assert sc.allowed_tools == ["read_file"]
        assert sc.max_tokens == 2048

    def test_system_prompt_forbids_self_gating(self) -> None:
        sc = build_openclaw_session_config(_persona(), [])
        assert "Never self-approve a gate" in sc.system_prompt


# ---------------------------------------------------------------------------
# FR-OCA-002 — tool policy mapping
# ---------------------------------------------------------------------------

class TestMapToolPolicy:
    def test_default_deny_without_enforcer(self) -> None:
        policy = map_tool_policy(["Read", "Write"])
        assert policy.allowlist == []
        assert "read_file" in policy.denylist
        assert "write_file" in policy.denylist

    def test_enforcer_allows_mapped_tools(self) -> None:
        policy = map_tool_policy(["Read", "Bash"], _AllowEnforcer())
        assert "read_file" in policy.allowlist
        assert "shell" in policy.allowlist
        assert policy.denylist == []

    def test_enforcer_deny_lists_tool(self) -> None:
        policy = map_tool_policy(["Read"], _DenyEnforcer())
        assert policy.allowlist == []
        assert "read_file" in policy.denylist

    def test_warned_decision_is_denied(self) -> None:
        # FR-OCA-002 is fail-closed: only ALLOWED reaches the allowlist. A PROMPT
        # policy yields WARNED, which must NOT be treated as allowed. This pins the
        # boundary so a regression to `!= DENIED` would fail here.
        policy = map_tool_policy(["Read"], _WarnEnforcer())
        assert policy.allowlist == []
        assert "read_file" in policy.denylist

    def test_unmapped_tool_is_mismatch(self) -> None:
        policy = map_tool_policy(["Telepathy"], _AllowEnforcer())
        assert policy.mismatches == ["Telepathy"]
        assert policy.allowlist == []

    def test_wire_reverse_lookup(self) -> None:
        assert wire_to_abstract("read_file") == "Read"
        assert wire_to_abstract("unknown_tool") == "unknown_tool"


# ---------------------------------------------------------------------------
# FR-OCA-003 — webhook → Forge event bridge
# ---------------------------------------------------------------------------

class TestBridgeWebhook:
    def test_agent_stopped_becomes_completed(self) -> None:
        ev = bridge_webhook({"event": "agent.stopped", "session_id": "s1"})
        assert ev.kind == EventKind.AGENT_COMPLETED
        assert ev.aggregate_id == "s1"

    def test_agent_message_becomes_text_delta(self) -> None:
        ev = bridge_webhook(
            {"event": "agent.message", "session_id": "s2", "payload": {"text": "hi"}}
        )
        assert ev.kind == EventKind.TEXT_DELTA
        assert ev.payload["text"] == "hi"

    def test_tool_proposed_becomes_proposal(self) -> None:
        ev = bridge_webhook({
            "event": "tool.proposed",
            "session_id": "s3",
            "payload": {"tool": "read_file", "tool_use_id": "t1", "inputs": {"p": 1}},
        })
        assert isinstance(ev, ToolUseProposal)
        assert ev.abstract_tool == "Read"
        assert ev.tool_use_id == "t1"
        assert ev.inputs == {"p": 1}

    def test_agent_failed_becomes_failed(self) -> None:
        ev = bridge_webhook(
            {"event": "agent.failed", "session_id": "s4", "payload": {"reason": "boom"}}
        )
        assert ev.kind == EventKind.AGENT_FAILED
        assert ev.payload["reason"] == "boom"

    def test_unknown_event_raises(self) -> None:
        # An unrecognized kind fails loud rather than being silently dropped.
        with pytest.raises(OpenClawError, match="unknown OpenClaw webhook event"):
            bridge_webhook({"event": "totally.unknown", "session_id": "s5"})


# ---------------------------------------------------------------------------
# FR-OCA-005 — memory separation
# ---------------------------------------------------------------------------

class TestMemorySeparation:
    def test_protected_paths_recognized(self) -> None:
        assert is_protected_path(".forge/state.json")
        assert is_protected_path("pipeline/gates.yaml")
        assert is_protected_path("./.forge/state.json")
        assert is_protected_path(".forge/security-audit.jsonl")
        # Core append-only memory of record (CLAUDE.md / SCHEMAS.md canonical set).
        assert is_protected_path(".forge/session-log.jsonl")
        assert is_protected_path(".forge/patterns.jsonl")
        assert is_protected_path(".forge/config.yaml")
        # Canonicalization defeats trivial path spellings.
        assert is_protected_path(".forge//state.json")
        assert is_protected_path(".forge/../.forge/state.json")
        assert not is_protected_path("src/foo.py")
        # Absolute/escaping forms are not themselves "protected files" — sync rejects
        # them separately (see test_sync_refuses_protected_and_escaping_targets).
        assert not is_protected_path("/abs/.forge/state.json")

    def test_canonical_relpath(self) -> None:
        assert canonical_relpath(".forge//state.json") == ".forge/state.json"
        assert canonical_relpath("./.forge/state.json") == ".forge/state.json"
        assert canonical_relpath(".forge/../.forge/state.json") == ".forge/state.json"
        assert canonical_relpath("/abs/x") is None       # absolute
        assert canonical_relpath("../escape") is None     # tree-escaping
        assert canonical_relpath("") is None              # empty

    def test_state_json_is_protected_constant(self) -> None:
        assert ".forge/state.json" in FORGE_PROTECTED_FILES

    def test_sync_accepts_normal_insight(self, tmp_path: Path) -> None:
        accepted = sync_insights_back(
            [{"id": "ins-1", "note": "useful"}], tmp_path
        )
        assert accepted == ["ins-1"]
        out = (tmp_path / "openclaw" / "insights.jsonl").read_text()
        assert "ins-1" in out

    def test_sync_refuses_protected_and_escaping_targets(self, tmp_path: Path) -> None:
        # Seed a real state.json and prove no spelling of its path gets accepted.
        forge = tmp_path / ".forge"
        forge.mkdir()
        state = forge / "state.json"
        state.write_text('{"phase": "real"}')

        evil_targets = [
            ".forge/state.json",            # canonical
            "/x/.forge/state.json",         # absolute
            "../.forge/state.json",         # tree-escaping
            ".forge//state.json",           # double slash
            ".forge/../.forge/state.json",  # traversal back in-tree
            ".forge/session-log.jsonl",     # newly protected core memory
        ]
        accepted = sync_insights_back(
            [{"id": f"evil-{i}", "target": t} for i, t in enumerate(evil_targets)],
            tmp_path,
        )
        assert accepted == []
        assert state.read_text() == '{"phase": "real"}'  # untouched


# ---------------------------------------------------------------------------
# FR-KA-002 — capabilities
# ---------------------------------------------------------------------------

class TestCapabilities:
    def test_kernel_id_and_tools(self) -> None:
        caps = OpenClawAdapter().get_capabilities()
        assert isinstance(caps, KernelCapabilities)
        assert caps.kernel_id == "openclaw"
        assert caps.client_tools == list(OPENCLAW_TOOL_MAP.keys())

    def test_module_adapter_id(self) -> None:
        assert adapter_id == "openclaw"


# ---------------------------------------------------------------------------
# FR-OCA-006 — offline fallback
# ---------------------------------------------------------------------------

class TestOfflineFallback:
    def test_is_available_false_without_transport(self) -> None:
        assert OpenClawAdapter().is_available() is False

    def test_is_available_true_with_command(self) -> None:
        assert OpenClawAdapter(gateway_command=["echo", "x"]).is_available() is True

    def test_fallback_is_next_priority_adapter(self) -> None:
        assert OpenClawAdapter().offline_fallback() == "opencode"

    async def test_spawn_unavailable_yields_failed(self) -> None:
        events = await _drain(
            OpenClawAdapter().spawn_agent(_persona(), "ctx", ["Read"], "agg-off")
        )
        assert len(events) == 1
        assert events[0].kind == EventKind.AGENT_FAILED
        assert events[0].payload["reason"] == "openclaw_unavailable"
        assert events[0].payload["fallback_adapter"] == "opencode"

    async def test_spawn_start_failure_falls_back_without_leak(self, monkeypatch) -> None:
        # A configured gateway whose start() fails: spawn falls back cleanly AND the
        # partially-started client is stopped (no leaked subprocess) — FR-OCA-006.
        holder: dict[str, _FailingStartClient] = {}

        def _make_client(*args: Any, **kwargs: Any) -> _FailingStartClient:
            client = _FailingStartClient()
            holder["client"] = client
            return client

        monkeypatch.setattr(
            "forge_os.adapters.openclaw.adapter.ACPClient", _make_client
        )
        adapter = OpenClawAdapter(gateway_command=["/nonexistent/gateway"])
        assert adapter.is_available() is True  # configured, though unreachable
        events = await _drain(
            adapter.spawn_agent(_persona(), "ctx", ["Read"], "agg-startfail")
        )
        assert len(events) == 1
        assert events[0].kind == EventKind.AGENT_FAILED
        assert events[0].payload["reason"] == "openclaw_unavailable"
        assert holder["client"].stopped is True  # cleanup ran — no process leak


# ---------------------------------------------------------------------------
# FR-KA-001 / FR-OCA-001 — spawn_agent over the ACP transport
# ---------------------------------------------------------------------------

class TestSpawnAgent:
    async def test_session_text_complete(self) -> None:
        client = _FakeACPClient([
            {"update": {"sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "Hello "}}},
            {"update": {"sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "world"}}},
        ])
        adapter = OpenClawAdapter(client=client)
        events = await _drain(adapter.spawn_agent(_persona(), "ctx", ["Read"], "agg-1"))

        kinds = [e.kind for e in events]
        assert kinds[0] == EventKind.SESSION_STARTED
        assert EventKind.TEXT_DELTA in kinds
        assert kinds[-1] == EventKind.AGENT_COMPLETED
        texts = [e.payload["text"] for e in events if e.kind == EventKind.TEXT_DELTA]
        assert texts == ["Hello ", "world"]

    async def test_session_started_payload(self) -> None:
        adapter = OpenClawAdapter(client=_FakeACPClient([]))
        events = await _drain(adapter.spawn_agent(_persona(), "ctx", ["Read"], "agg-2"))
        started = events[0]
        assert started.kind == EventKind.SESSION_STARTED
        assert started.payload["kernel"] == "openclaw"
        assert started.payload["session_id"] == "oc-sess-1"

    async def test_thinking_delta(self) -> None:
        client = _FakeACPClient([
            {"update": {"sessionUpdate": "agent_thought_chunk",
                        "content": {"text": "reasoning"}}},
        ])
        events = await _drain(
            OpenClawAdapter(client=client).spawn_agent(_persona(), "c", ["Read"], "agg-3")
        )
        thinking = next(e for e in events if e.kind == EventKind.THINKING_DELTA)
        assert thinking.payload["thinking"] == "reasoning"

    async def test_tool_proposal_then_complete(self) -> None:
        client = _FakeACPClient([
            {"update": {"sessionUpdate": "tool_call", "toolCallId": "tc-1",
                        "kind": "read_file", "rawInput": {"path": "/tmp/x"}}},
        ])
        events = await _drain(
            OpenClawAdapter(client=client).spawn_agent(_persona(), "c", ["Read"], "agg-4")
        )
        proposal = next(e for e in events if isinstance(e, ToolUseProposal))
        assert proposal.abstract_tool == "Read"
        assert proposal.tool_use_id == "tc-1"
        assert proposal.inputs == {"path": "/tmp/x"}
        assert events[-1].kind == EventKind.AGENT_COMPLETED

    async def test_error_update_yields_failed(self) -> None:
        client = _FakeACPClient([
            {"update": {"sessionUpdate": "error", "message": "boom"}},
        ])
        events = await _drain(
            OpenClawAdapter(client=client).spawn_agent(_persona(), "c", ["Read"], "agg-5")
        )
        assert events[-1].kind == EventKind.AGENT_FAILED
        assert events[-1].payload["reason"] == "session_error"

    async def test_malformed_update_is_skipped_not_raised(self) -> None:
        # A hostile/buggy gateway sending non-dict update payloads must NOT escape as
        # an uncaught AttributeError — they are skipped and the turn completes cleanly.
        client = _FakeACPClient([
            {"update": "oops-not-a-dict"},
            "not-a-dict-param",
            {"update": {"sessionUpdate": "agent_message_chunk",
                        "content": {"text": "ok"}}},
        ])
        events = await _drain(
            OpenClawAdapter(client=client).spawn_agent(_persona(), "c", ["Read"], "agg-mal")
        )
        assert events[-1].kind == EventKind.AGENT_COMPLETED
        texts = [e.payload["text"] for e in events if e.kind == EventKind.TEXT_DELTA]
        assert texts == ["ok"]

    async def test_prompt_error_midstream_yields_failed(self) -> None:
        # FR-OCA-006: a transport error mid-stream normalizes to AGENT_FAILED rather
        # than propagating and corrupting/advancing Forge state.
        class _RaisingClient:
            session_id = "s"

            def prompt(self, prompt_text: str, session_id: str | None = None):
                yield {"update": {"sessionUpdate": "agent_message_chunk",
                                  "content": {"text": "partial"}}}
                raise ACPClientError("stream broke")

        events = await _drain(
            OpenClawAdapter(client=_RaisingClient()).spawn_agent(
                _persona(), "c", ["Read"], "agg-mid"
            )
        )
        assert events[-1].kind == EventKind.AGENT_FAILED
        assert events[-1].payload["reason"] == "openclaw_error"

    async def test_non_tool_result_send_raises(self) -> None:
        client = _FakeACPClient([
            {"update": {"sessionUpdate": "tool_call", "toolCallId": "tc-9",
                        "kind": "read_file"}},
        ])
        agen = OpenClawAdapter(client=client).spawn_agent(
            _persona(), "c", ["Read"], "agg-6"
        )
        # Advance to the proposal, then send a bad value back.
        ev = await agen.asend(None)
        while not isinstance(ev, ToolUseProposal):
            ev = await agen.asend(None)
        with pytest.raises(OpenClawError, match="expected ToolResult"):
            await agen.asend("not-a-tool-result")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ACP session management reuse
# ---------------------------------------------------------------------------

class TestSessionManagement:
    def test_list_resume_close_delegate_to_acp(self) -> None:
        client = _FakeACPClient(
            [], sessions=[SessionInfo(id="s1", title="t1")]
        )
        adapter = OpenClawAdapter(client=client)
        assert adapter.list_sessions() == [{"id": "s1", "title": "t1", "metadata": {}}]
        adapter.resume_session("s1")
        adapter.close_session("s1")
        assert client.resumed == ["s1"]
        assert client.closed == ["s1"]

    def test_list_sessions_empty_when_unavailable(self) -> None:
        assert OpenClawAdapter().list_sessions() == []


# ---------------------------------------------------------------------------
# FR-KA-005 — lifecycle hooks
# ---------------------------------------------------------------------------

class TestLifecycleHooks:
    async def test_on_event_no_error(self) -> None:
        await OpenClawAdapter().on_event(
            NormalizedEvent(kind=EventKind.SESSION_STARTED, aggregate_id="x")
        )

    async def test_sync_memory_no_op(self) -> None:
        await OpenClawAdapter().sync_memory()
        await OpenClawAdapter().sync_memory(lkg_snapshot={"k": "v"})


# ---------------------------------------------------------------------------
# FR-OCA-004 — channel reuse
# ---------------------------------------------------------------------------

class TestChannelReuse:
    def test_channel_id(self) -> None:
        assert OpenClawChannelAdapter().channel_id == "openclaw"

    def test_inbound_message_normalized_untrusted(self) -> None:
        event = OpenClawChannelAdapter().on_message("hello", sender="u1")
        # normalize_message produces a UserPromptSubmit lifecycle event.
        assert event.payload["channel_id"] == "openclaw"
        assert event.payload["trust_level"] == "untrusted"

    def test_outbound_buffered(self) -> None:
        channel = OpenClawChannelAdapter()
        channel.send_message("ping")
        assert channel.sent == ["ping"]


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_factory_requires_gateway(self, tmp_path: Path) -> None:
        with pytest.raises(AdapterRegistryError, match="gateway endpoint"):
            get_adapter_registry().create("openclaw", tmp_path, {})

    def test_factory_constructs_with_command(self, tmp_path: Path) -> None:
        adapter = get_adapter_registry().create(
            "openclaw", tmp_path, {"gateway_command": ["echo", "hi"]}
        )
        assert not isinstance(adapter, PlaceholderAdapter)

    def test_factory_rejects_url_only(self, tmp_path: Path) -> None:
        # Only the stdio gateway_command transport is wired in v0.1; a url-only config
        # must fail so `forge adapter status` does not report a non-functional adapter.
        with pytest.raises(AdapterRegistryError, match="gateway_command"):
            get_adapter_registry().create(
                "openclaw", tmp_path, {"gateway_url": "http://localhost:9999"}
            )

    def test_factory_rejects_empty_command(self, tmp_path: Path) -> None:
        with pytest.raises(AdapterRegistryError, match="gateway_command"):
            get_adapter_registry().create("openclaw", tmp_path, {"gateway_command": []})
