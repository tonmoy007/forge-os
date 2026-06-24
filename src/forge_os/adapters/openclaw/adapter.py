"""OpenClawAdapter — optional execution surface built on the Phase 08 ACP foundation.

Phase 11, Slice 3 (FR-OCA-001..006, tasks P11.08-14).

OpenClaw is integrated *only* through the Kernel Adapter interface and must never
become a required dependency (``plan/OPENCLAW_ADAPTER_ARCHITECTURE.md``). The
adapter owns **translation only** — Forge OS Core keeps state, gate decisions, and
the memory source-of-truth.

Status of this slice
--------------------
No concrete OpenClaw HTTP/WebSocket wire protocol, auth scheme, or webhook payload
contract is published yet (P11.08 is blocked on that). So this is a **scaffold**:
the full interface, persona/tool translation, webhook→event bridge, memory-safety
guard, and offline fallback are real and tested; the transport reuses the Phase 08
``ACPClient`` (stdio JSON-RPC) via ``gateway_command`` for session management. The
HTTP/WebSocket transport to a remote Gateway is deferred to P11.08 (no endpoint
contract exists yet) — no dead config is carried for it and no wire protocol is
invented here.

How it maps onto the ACP foundation
------------------------------------
    OpenClaw session start   → ACPClient.prompt() (session/prompt)
    OpenClaw session listing  → ACPClient.session_list()
    OpenClaw resume / close   → ACPClient.session_resume() / session_close()
    OpenClaw streaming output → ACP session/update notifications → NormalizedEvent

OpenClaw Gateways that speak ACP plug in with zero extra code. Gateways that speak
a bespoke HTTP/WS protocol will need a thin transport shim (TODO, P11.08) — the rest
of this adapter is transport-agnostic.
"""

from __future__ import annotations

import json
import logging
import posixpath
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from forge_os.adapters.registry import ADAPTER_PRIORITY
from forge_os.kernel.acp_client import ACPClient, ACPClientError
from forge_os.kernel.types import (
    AgentPersona,
    EventKind,
    IKernelAdapter,
    KernelCapabilities,
    NormalizedEvent,
    ToolResult,
    ToolUseProposal,
)
from forge_os.schemas.openclaw import (
    OpenClawSessionConfig,
    OpenClawToolPolicy,
    OpenClawWebhook,
    OpenClawWebhookKind,
)
from forge_os.schemas.security import SecurityDecision

log = logging.getLogger("forge.adapters.openclaw")

adapter_id = "openclaw"


class OpenClawError(RuntimeError):
    """Raised on OpenClaw translation/bridge failures (e.g. an unknown webhook)."""


# ---------------------------------------------------------------------------
# Tool registry (FR-OCA-002) — abstract Forge tool → OpenClaw wire name.
# Anything requested but absent here is a *mismatch*: logged and denied
# (fail-closed), never silently forwarded.
# ---------------------------------------------------------------------------

OPENCLAW_TOOL_MAP: dict[str, str] = {
    "Read": "read_file",
    "Write": "write_file",
    "Edit": "edit_file",
    "Bash": "shell",
    "Grep": "search",
    "Glob": "glob",
    "WebFetch": "web_fetch",
}


# ---------------------------------------------------------------------------
# Memory separation (FR-OCA-005). OpenClaw's optional native memory must never
# overwrite these Forge source-of-truth artifacts; insights are *proposed* into a
# side-channel and Forge Core decides whether to persist them.
# ---------------------------------------------------------------------------

FORGE_PROTECTED_FILES: frozenset[str] = frozenset({
    ".forge/config.yaml",
    ".forge/state.json",
    ".forge/events.jsonl",
    ".forge/session-log.jsonl",
    ".forge/patterns.jsonl",
    ".forge/lessons.yaml",
    "pipeline/state.md",
    "pipeline/gates.yaml",
    "pipeline/stages.yaml",
    "pipeline/dependencies.graphml",
})


def canonical_relpath(path: str) -> str | None:
    """Normalize ``path`` to a project-relative POSIX path, collapsing ``.``/``..``.

    Returns None for an empty, absolute, or tree-escaping path — none of which can
    safely name a project-relative source-of-truth file. This is the canonical form
    the memory-separation guard compares against, so trivial spellings
    (``./``, ``//``, ``a/../b``) cannot slip a protected target past it (FR-OCA-005).
    """
    raw = path.replace("\\", "/").strip()
    if not raw or raw.startswith("/"):
        return None
    normalized = posixpath.normpath(raw)
    if normalized == ".." or normalized.startswith("../"):
        return None
    return normalized


def is_protected_path(path: str) -> bool:
    """True if ``path`` resolves to a Forge source-of-truth file OpenClaw may not write."""
    rel = canonical_relpath(path)
    if rel is None:
        return False
    if rel in FORGE_PROTECTED_FILES:
        return True
    # Any audit log under .forge/ ending in -audit.jsonl is also protected.
    return rel.startswith(".forge/") and rel.endswith("-audit.jsonl")


def wire_to_abstract(wire: str) -> str:
    """Reverse-lookup an OpenClaw wire tool name → Forge abstract name."""
    for abstract, mapped in OPENCLAW_TOOL_MAP.items():
        if mapped == wire:
            return abstract
    return wire  # unknown — pass through unchanged


def build_openclaw_session_config(
    persona: AgentPersona,
    allowed_tools: list[str],
    denied_tools: list[str] | None = None,
) -> OpenClawSessionConfig:
    """Project a Forge persona onto an OpenClaw agent session config (FR-OCA-001).

    OpenClaw configures agents with ``SOUL.md`` (identity/voice) and ``IDENTITY.md``
    (role/goal) documents plus a system prompt. This keeps the persona
    kernel-agnostic — the same ``AgentPersona`` runs on any adapter.
    """
    constraints = "\n".join(f"- {c}" for c in persona.constraints) or "(none)"
    contract = json.dumps(persona.output_contract or {}, indent=2)
    soul_md = (
        f"# SOUL\n\n"
        f"You are **{persona.name}**, an agent operating inside Forge OS via the "
        f"OpenClaw kernel.\n\n## Voice\n{persona.role}\n"
    )
    identity_md = (
        f"# IDENTITY\n\n## Role\n{persona.role}\n\n## Goal\n{persona.goal}\n\n"
        f"## Constraints\n{constraints}\n"
    )
    system_prompt = (
        f"# Role\n{persona.role}\n\n# Goal\n{persona.goal}\n\n"
        f"# Constraints\n{constraints}\n\n"
        f"# Output contract\n```json\n{contract}\n```\n\n"
        "# Operating principles\n"
        "- You run inside Forge OS via the OpenClaw kernel.\n"
        "- Every tool call is gated by Forge's Validator; denied tools return an "
        "error result — do not retry the same call.\n"
        "- Forge OS decides all gates. Never self-approve a gate.\n"
    )
    return OpenClawSessionConfig(
        agent_name=persona.name,
        soul_md=soul_md,
        identity_md=identity_md,
        system_prompt=system_prompt,
        model=persona.preferred_model,
        allowed_tools=list(allowed_tools),
        denied_tools=list(denied_tools or []),
        max_tokens=persona.max_tokens,
        temperature=persona.temperature,
    )


def map_tool_policy(
    requested_tools: list[str],
    enforcer: Any = None,
    actor: dict[str, Any] | None = None,
) -> OpenClawToolPolicy:
    """Map Forge tool categories to OpenClaw's allow/deny lists (FR-OCA-002).

    Default-deny: a tool reaches the allowlist only when (a) it has an OpenClaw
    wire mapping AND (b) the SecurityEnforcer returns ALLOWED for it. Tools with
    no mapping are *mismatches* (logged, excluded). With no enforcer supplied,
    every mapped tool is denied (fail-closed).
    """
    actor = actor or {"type": "openclaw", "id": "adapter"}
    policy = OpenClawToolPolicy()
    for tool in requested_tools:
        wire = OPENCLAW_TOOL_MAP.get(tool)
        if wire is None:
            policy.mismatches.append(tool)
            log.warning("openclaw: no tool mapping for %r — denied", tool)
            continue
        decision = (
            enforcer.validate_action(actor, "use_tool", target=tool, capability=tool)
            if enforcer is not None
            else SecurityDecision.DENIED
        )
        if decision == SecurityDecision.ALLOWED:
            policy.allowlist.append(wire)
        else:
            policy.denylist.append(wire)
    if policy.mismatches:
        log.warning("openclaw: %d tool mismatch(es): %s", len(policy.mismatches),
                    policy.mismatches)
    return policy


def bridge_webhook(webhook: OpenClawWebhook | dict[str, Any]) -> NormalizedEvent:
    """Translate an OpenClaw Gateway webhook into a Forge lifecycle event (FR-OCA-003).

    ``agent.stopped`` becomes ``AGENT_COMPLETED`` — the Forge ``Stop`` signal that
    triggers reflection, gate checks, and lesson extraction. Unknown event kinds
    fail loud rather than being silently dropped.
    """
    if isinstance(webhook, OpenClawWebhook):
        event: str = webhook.event
        session_id = webhook.session_id
        payload = webhook.payload
    else:
        event = str(webhook.get("event", ""))
        session_id = str(webhook.get("session_id", ""))
        payload = webhook.get("payload", {}) or {}

    # StrEnum compares equal to its raw value, so this dispatch works whether the
    # caller passed a typed OpenClawWebhook or a raw dict from the wire.
    if event == OpenClawWebhookKind.AGENT_MESSAGE:
        return NormalizedEvent(
            kind=EventKind.TEXT_DELTA,
            aggregate_id=session_id,
            payload={"text": payload.get("text", "")},
        )
    if event == OpenClawWebhookKind.TOOL_PROPOSED:
        wire = str(payload.get("tool", ""))
        return ToolUseProposal(
            kind=EventKind.TOOL_USE_PROPOSED,
            aggregate_id=session_id,
            tool_use_id=str(payload.get("tool_use_id", wire)),
            tool_name=wire,
            abstract_tool=wire_to_abstract(wire),
            inputs=payload.get("inputs", {}) or {},
        )
    if event == OpenClawWebhookKind.AGENT_STOPPED:
        return NormalizedEvent(
            kind=EventKind.AGENT_COMPLETED,
            aggregate_id=session_id,
            payload={"session_id": session_id, "source": "openclaw_webhook"},
        )
    if event == OpenClawWebhookKind.AGENT_FAILED:
        return NormalizedEvent(
            kind=EventKind.AGENT_FAILED,
            aggregate_id=session_id,
            payload={
                "reason": payload.get("reason", "openclaw_agent_failed"),
                "session_id": session_id,
            },
        )
    raise OpenClawError(f"unknown OpenClaw webhook event: {event!r}")


def sync_insights_back(insights: list[dict[str, Any]], forge_dir: Path) -> list[str]:
    """Append OpenClaw-proposed insights to ``.forge/openclaw/insights.jsonl`` (FR-OCA-005).

    Insights are *proposals* — Forge Core decides whether to promote them. An
    insight whose ``target`` names a protected source-of-truth file — or any
    absolute / tree-escaping path that could reach one — is refused, so OpenClaw's
    native memory can never overwrite Forge's authoritative artifacts.
    Returns the ids/titles of accepted insights.
    """
    out_dir = forge_dir / "openclaw"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "insights.jsonl"

    accepted: list[str] = []
    rejected: list[str] = []
    with path.open("a", encoding="utf-8") as handle:
        for insight in insights:
            target = insight.get("target")
            if isinstance(target, str) and target.strip():
                rel = canonical_relpath(target)
                # rel is None for absolute/escaping targets (can't be proven safe);
                # otherwise check the canonical form against the protected set.
                if rel is None or is_protected_path(rel):
                    rejected.append(target)
                    continue
            handle.write(json.dumps(insight, ensure_ascii=False) + "\n")
            accepted.append(str(insight.get("id") or insight.get("title") or ""))
    if rejected:
        log.warning("openclaw: refused %d insight(s) targeting protected/out-of-tree "
                    "files: %s", len(rejected), rejected)
    return accepted


class OpenClawAdapter(IKernelAdapter):
    """Optional OpenClaw execution adapter (FR-OCA-001..006).

    Transport: an injected or lazily-constructed :class:`ACPClient`. With no
    reachable transport the adapter is *unavailable* and ``spawn_agent`` emits a
    normalized ``AGENT_FAILED`` so the orchestrator can fall back without
    corrupting Forge state (FR-OCA-006).
    """

    KERNEL_ID = "openclaw"

    def __init__(
        self,
        gateway_command: list[str] | None = None,
        *,
        client: ACPClient | None = None,
        default_model: str = "claude-opus-4-7",
        security_enforcer: Any = None,
        actor: dict[str, Any] | None = None,
        forge_dir: Path | None = None,
        request_timeout_s: float = 30.0,
    ) -> None:
        # v0.1 wires the stdio ACP transport (gateway_command). The HTTP/WebSocket
        # transport to a remote Gateway is deferred to P11.08 (no endpoint contract
        # exists yet) — see the module docstring; no dead config is carried for it.
        self._gateway_command = list(gateway_command) if gateway_command else []
        self._client = client
        self._default_model = default_model
        self._enforcer = security_enforcer
        self._actor = actor or {"type": "openclaw", "id": "adapter"}
        self._forge_dir = forge_dir or (Path.home() / ".forge")
        self._request_timeout = request_timeout_s

    # ---- FR-OCA-002 / 003 / 005 instance helpers ----------------------------

    def map_tool_policy(self, requested_tools: list[str]) -> OpenClawToolPolicy:
        return map_tool_policy(requested_tools, self._enforcer, self._actor)

    def bridge_webhook(self, webhook: OpenClawWebhook | dict[str, Any]) -> NormalizedEvent:
        return bridge_webhook(webhook)

    def sync_insights_back(self, insights: list[dict[str, Any]]) -> list[str]:
        return sync_insights_back(insights, self._forge_dir)

    # ---- transport ----------------------------------------------------------

    def is_available(self) -> bool:
        """True if a transport is *configured* (injected client or stdio command).

        Configured ≠ reachable; reachability is proven at ``spawn_agent`` time.
        """
        return self._client is not None or bool(self._gateway_command)

    def _ensure_client(self) -> ACPClient | None:
        """Return a started ACP transport, or None if OpenClaw is unreachable."""
        if self._client is not None:
            return self._client
        if not self._gateway_command:
            return None
        client = ACPClient(self._gateway_command, response_timeout=self._request_timeout)
        try:
            client.start()
        except (ACPClientError, OSError) as exc:
            # start() may have spawned the subprocess before failing in initialize;
            # stop() (a no-op when no process exists) prevents leaking it.
            client.stop()
            log.warning("openclaw: gateway unreachable (%s) — falling back", exc)
            return None
        self._client = client
        return client

    def offline_fallback(self) -> str | None:
        """The next adapter id after ``openclaw`` in priority order (FR-OCA-006)."""
        try:
            idx = ADAPTER_PRIORITY.index(self.KERNEL_ID)
        except ValueError:
            return None
        nxt = ADAPTER_PRIORITY[idx + 1 :]
        return nxt[0] if nxt else None

    # ---- ACP session management reuse ---------------------------------------

    def list_sessions(self) -> list[dict[str, Any]]:
        client = self._ensure_client()
        if client is None:
            return []
        return [{"id": s.id, "title": s.title, "metadata": s.metadata}
                for s in client.session_list()]

    def resume_session(self, session_id: str) -> None:
        client = self._ensure_client()
        if client is None:
            raise OpenClawError("OpenClaw unavailable: cannot resume session")
        client.session_resume(session_id)

    def close_session(self, session_id: str) -> None:
        client = self._ensure_client()
        if client is None:
            return
        client.session_close(session_id)

    # ---- FR-KA-002 ----------------------------------------------------------

    def get_capabilities(self) -> KernelCapabilities:
        return KernelCapabilities(
            kernel_id=self.KERNEL_ID,
            streaming=True,
            deterministic_output=False,
            extended_thinking=True,
            prompt_caching=True,
            vision=False,
            batch_api=False,
            hooks_native=True,           # OpenClaw webhooks → Forge events
            subagents_native=True,
            mcp_remote=True,
            mcp_local_stdio=True,
            client_tools=list(OPENCLAW_TOOL_MAP.keys()),
            server_tools=[],
            max_context_tokens=200_000,
            notes={
                "optional": (
                    "OpenClaw is an optional execution surface; its failure never "
                    "advances or corrupts Forge state (FR-OCA-006)."
                ),
                "gates": (
                    "Tool/gate requests are forwarded to Forge Core; OpenClaw never "
                    "decides gates internally (architecture: Gate Rule)."
                ),
                "transport_placeholder": (
                    "HTTP/WebSocket transport to a remote Gateway is a documented "
                    "placeholder pending P11.08; the stdio ACP transport "
                    "(gateway_command) is wired."
                ),
            },
        )

    # ---- FR-KA-001 / FR-OCA-001 ---------------------------------------------

    async def spawn_agent(
        self,
        persona: AgentPersona,
        context: str,
        tools: list[str],
        aggregate_id: str,
        *,
        timeout_s: float = 600.0,
    ) -> AsyncIterator[NormalizedEvent]:
        """Run one OpenClaw agent turn and yield normalized events.

        Tool proposals are yielded at the Proposal boundary; the caller asend()s a
        ToolResult that this adapter relays to the Gateway. Forge Core owns the
        decision — the adapter never inspects or overrides it.
        """
        client = self._ensure_client()
        if client is None:
            # FR-OCA-006: unreachable → normalized failure, state untouched.
            yield NormalizedEvent(
                kind=EventKind.AGENT_FAILED,
                aggregate_id=aggregate_id,
                payload={
                    "reason": "openclaw_unavailable",
                    "fallback_adapter": self.offline_fallback(),
                    "detail": "OpenClaw Gateway not reachable; Forge state unchanged.",
                },
            )
            return

        allowed_abstract = [t for t in persona.allowed_tools if t in set(tools)]
        policy = self.map_tool_policy(allowed_abstract)
        session_config = build_openclaw_session_config(persona, policy.allowlist)
        session_id = client.session_id or aggregate_id

        yield NormalizedEvent(
            kind=EventKind.SESSION_STARTED,
            aggregate_id=aggregate_id,
            payload={
                "persona": persona.name,
                "model": session_config.model,
                "kernel": self.KERNEL_ID,
                "session_id": session_id,
                "agent": session_config.agent_name,
                "client_tools": allowed_abstract,
                "tool_mismatches": policy.mismatches,
            },
        )

        try:
            updates = client.prompt(context, session_id=session_id)
            while True:
                try:
                    params = next(updates)
                except StopIteration:
                    break
                event = self._translate_update(params, aggregate_id)
                if event is None:
                    continue
                if isinstance(event, ToolUseProposal):
                    result = yield event  # caller does asend(ToolResult)
                    if not isinstance(result, ToolResult):
                        raise OpenClawError(
                            f"spawn_agent expected ToolResult, got {type(result)}"
                        )
                    # Relay the Forge-owned decision back to the Gateway. v0.1
                    # logs it; the respond endpoint lands with P11.08.
                    log.debug("openclaw tool decision relayed: id=%s is_error=%s",
                              result.tool_use_id, result.is_error)
                else:
                    yield event
                    if event.kind in (EventKind.AGENT_COMPLETED, EventKind.AGENT_FAILED):
                        return
        except ACPClientError as exc:
            yield NormalizedEvent(
                kind=EventKind.AGENT_FAILED,
                aggregate_id=aggregate_id,
                payload={"reason": "openclaw_error", "detail": repr(exc)},
            )
            return

        yield NormalizedEvent(
            kind=EventKind.AGENT_COMPLETED,
            aggregate_id=aggregate_id,
            payload={"session_id": session_id},
        )

    def _translate_update(
        self, params: dict[str, Any], aggregate_id: str
    ) -> NormalizedEvent | None:
        """Translate one ACP ``session/update`` notification → NormalizedEvent.

        Handles the documented subset OpenClaw Gateways emit; unrecognized update
        kinds — and malformed non-dict payloads from a hostile/buggy gateway — are
        ignored (returned as None) rather than escaping as an uncaught error.
        """
        if not isinstance(params, dict):
            return None
        update = params.get("update", params)
        if not isinstance(update, dict):
            return None
        kind = update.get("sessionUpdate") or update.get("type")

        if kind in ("agent_message_chunk", "message", "text"):
            text = _extract_text(update)
            return (
                NormalizedEvent(EventKind.TEXT_DELTA, aggregate_id, {"text": text})
                if text else None
            )
        if kind in ("agent_thought_chunk", "thinking", "thought"):
            text = _extract_text(update)
            return (
                NormalizedEvent(EventKind.THINKING_DELTA, aggregate_id, {"thinking": text})
                if text else None
            )
        if kind in ("tool_call", "tool_call_update", "tool"):
            wire = str(update.get("kind") or update.get("toolName")
                       or update.get("title") or "")
            tool_id = str(update.get("toolCallId") or update.get("id") or wire)
            inputs = update.get("rawInput") or update.get("input") or update.get("inputs") or {}
            return ToolUseProposal(
                kind=EventKind.TOOL_USE_PROPOSED,
                aggregate_id=aggregate_id,
                tool_use_id=tool_id,
                tool_name=wire,
                abstract_tool=wire_to_abstract(wire),
                inputs=inputs,
            )
        if kind in ("error", "session_error"):
            return NormalizedEvent(
                kind=EventKind.AGENT_FAILED,
                aggregate_id=aggregate_id,
                payload={"reason": "session_error", "detail": update},
            )
        return None

    # ---- FR-KA-005: on_event ------------------------------------------------

    async def on_event(self, event: NormalizedEvent) -> None:
        """Forge lifecycle events arriving at the kernel. v0.1: log only."""
        log.debug("openclaw on_event: %s aggregate=%s", event.kind, event.aggregate_id)

    # ---- FR-KA-001: sync_memory ---------------------------------------------

    async def sync_memory(self, lkg_snapshot: dict[str, Any] | None = None) -> None:
        """No-op: Forge's LKG is authoritative (FR-OCA-005).

        OpenClaw insights are proposed back via ``sync_insights_back`` and Forge
        Core decides whether to persist them — never the reverse.
        """
        return None


def _extract_text(update: dict[str, Any]) -> str:
    """Pull text out of an ACP update's ``content`` (str | {type,text} | text field)."""
    content = update.get("content")
    if isinstance(content, dict):
        return str(content.get("text", ""))
    if isinstance(content, str):
        return content
    return str(update.get("text", ""))
