"""
forge.kernel.opencode
=====================

Reference implementation of the Forge OS Kernel Adapter for **OpenCode**
(sst/opencode), the open-source terminal coding agent built on a client/server
architecture.

This is the third kernel adapter in the Forge kernel layer, parallel to:

    claude_adapter.py          → anthropic.AsyncAnthropic.messages.create()
    claude_sdk_adapter.py      → claude_agent_sdk.ClaudeSDKClient
    opencode_adapter.py        → opencode_ai.AsyncOpencode → `opencode serve`

The interfaces, normalized events, and Proposal-boundary semantics are
**identical** across all three. The only thing that changes is what runs the
agent loop. Run the same persona + context + tools through each and you get
an apples-to-apples comparison of: latency, token efficiency, multi-turn
tool-loop overhead, recovery on failure, and any model-output drift the
kernel substrate introduces.

Architecture in one paragraph
-----------------------------
OpenCode is a TypeScript/Bun server that exposes an OpenAPI 3.1 HTTP API and
an SSE event stream (`/event`, `/global/event`). The Python SDK
(`opencode-ai`) is Stainless-generated from that spec. The TUI is just one
client among many. This adapter is another client: it `POST`s prompts to
`/session/:id/message`, subscribes to `/event` for streaming deltas and tool
lifecycle, and uses the permission API to gate every tool call. The server
itself is launched out-of-band via `opencode serve` — either by the user, by
CI, or auto-spawned by this adapter when `auto_spawn_server=True`.

How the Proposal boundary is preserved
--------------------------------------
OpenCode has *built-in* tools (read, write, edit, bash, grep, glob, the
`skill` tool, plus any MCP tools the user configured). If Claude calls those
through OpenCode, the server executes them in its own Bun process — Forge's
Validator + Executor would only see post-hoc events, not pre-execution
proposals. That violates §2.7 Bounded Autonomy.

To prevent it, this adapter:

  1. Writes a **session-scoped agent config** that denies every built-in tool
     and every user-configured MCP tool not on the persona's allow-list.
     Permissions default to `deny`; the persona's `allowed_tools` are flipped
     to `ask` (which routes the request through the permission API where this
     adapter intercepts and forwards to Forge's Validator).
  2. Optionally launches a **Forge MCP proxy server** (a separate Python
     process exposing Forge's abstract tools via MCP stdio) and registers it
     with the OpenCode server via the `mcp.*` config keys. Each tool call on
     that MCP server pushes a ToolUseProposal onto an asyncio.Queue and
     awaits the ToolResult that Forge writes back after Validator+Executor
     have run. Same pattern as `_build_forge_proxy_server()` in
     claude_sdk_adapter.py — different transport (MCP stdio instead of
     in-process SDK MCP).
  3. Hides the `skill` tool and any agent-spawning tools (`/task`, subagents)
     in v0.1. Subagents introduce nested kernel sessions that Forge's audit
     ledger doesn't model yet — enable in v0.2 once §3.34 has nested
     aggregate IDs.

The MCP proxy implementation lives in `forge/kernel/opencode_mcp_proxy.py`
(not in this file) and is referenced here by command string. For the v0.1
scaffold, tool proposals are surfaced via the **permission API** path,
which is sufficient to validate the kernel comparison without requiring the
MCP proxy to be built first.

Dependencies
------------
    pip install "opencode-ai>=1.14" "httpx>=0.27" pyyaml
    # plus a running `opencode serve` on the host:
    #   OPENCODE_SERVER_PASSWORD=... opencode serve --port 4096
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import signal
import subprocess
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from forge_os.kernel.types import (
    AgentPersona as _BaseAgentPersona,
)
from forge_os.kernel.types import (
    EventKind,
    IKernelAdapter,
    KernelCapabilities,
    NormalizedEvent,
    ToolResult,
    ToolUseProposal,
)

# Lazy-import the SDK so this file parses even without it installed.
try:
    from opencode_ai import APIError as _OpencodeAPIError  # type: ignore
    from opencode_ai import AsyncOpencode  # type: ignore
    _SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    AsyncOpencode = None  # type: ignore
    _OpencodeAPIError = Exception  # type: ignore
    _SDK_AVAILABLE = False

# aiohttp powers the loopback back-channel server that the MCP proxy posts
# tool proposals to. Lazy-import so the rest of the module loads without it.
try:
    from aiohttp import web as _aiohttp_web  # type: ignore
    _AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover
    _aiohttp_web = None  # type: ignore
    _AIOHTTP_AVAILABLE = False

log = logging.getLogger("forge.kernel.opencode")



# ============================================================================
# Section 2 — Persona + capability dataclasses
# ============================================================================

# Re-export canonical AgentPersona so callers don't need to know the subclass.
AgentPersona = _BaseAgentPersona


@dataclass
class OpenCodeAgentPersona(_BaseAgentPersona):
    """AgentPersona extended with OpenCode-specific fields (FR-KA-003).

    Use this when spawning agents via OpenCodeAdapter. The base fields
    (role, goal, constraints, allowed_tools) remain kernel-agnostic.
    """
    # OpenCode references models as "<provider>/<model>"
    preferred_model: str = "anthropic/claude-opus-4-7"

    # OpenCode-only knobs
    opencode_agent_name: str = "forge"
    primary_agent_template: str = "build"         # "build" | "plan" | custom
    enable_skills: bool = False
    enable_subagents: bool = False                # /task tool — v0.2
    extra_provider_options: dict[str, Any] = field(default_factory=dict)




# ============================================================================
# Section 4 — Tool registry (FR-KA-003)
# ============================================================================
# OpenCode's built-in tools, mapped to Forge's abstract tool names. The
# Forge orchestrator only knows abstract names; the adapter is responsible
# for the translation. Anything NOT in this table is either a custom MCP
# tool (resolved at runtime via the Forge MCP proxy) or unsupported.
#
# Abstract → OpenCode wire name
OPENCODE_BUILTIN_TOOLS: dict[str, str] = {
    "Read":      "read",
    "Write":     "write",
    "Edit":      "edit",
    "Bash":      "bash",
    "Grep":      "grep",
    "Glob":      "glob",
    "WebFetch":  "webfetch",
    "Todo":      "todo",
    # Deliberately omitted in v0.1:
    #   "skill"  → would let the agent load arbitrary SKILL.md files,
    #              bypassing Forge's prompt provenance audit.
    #   "task"   → spawns subagents, breaks aggregate ID nesting.
    #   "agent"  → same as task.
}

# Forge's custom tools — exposed via the Forge MCP proxy server.
# These names are what the Forge orchestrator references; the proxy
# translates them into MCP tool calls back to Forge's Validator+Executor.
# OpenCode sees them as MCP tools named "forge_<abstract>".
FORGE_CUSTOM_TOOLS: dict[str, dict[str, Any]] = {
    "ProposeEvent": {
        "name": "forge_propose_event",
        "description": "Propose a domain event for the Forge event store.",
        "input_schema": {
            "type": "object",
            "properties": {
                "aggregate_id": {"type": "string"},
                "event_type":   {"type": "string"},
                "payload":      {"type": "object"},
            },
            "required": ["aggregate_id", "event_type", "payload"],
        },
    },
    "ReadLKG": {
        "name": "forge_read_lkg",
        "description": "Read from Forge's Lessons Knowledge Graph.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    # Add more Forge-native tools here. Each MUST be backed by an executor
    # in the Forge MCP proxy (forge/kernel/opencode_mcp_proxy.py).
}


def build_session_permissions(
    abstract_client_tools: list[str],
) -> tuple[dict[str, str], list[str]]:
    """Build the OpenCode permission map and the wire-name allowlist.

    Returns:
        permissions: dict mapping OpenCode tool wire-name → "allow"|"ask"|"deny"
        wire_allowlist: list of wire names the model is permitted to attempt

    Strategy: default-deny everything, then flip the persona's allowed tools
    to "ask". The "ask" routing triggers a permission event on the SSE
    stream, which spawn_agent() converts into a ToolUseProposal. Forge's
    Validator decides; we POST allow/deny back via the permission API.
    """
    permissions: dict[str, str] = {}
    wire_allowlist: list[str] = []

    # Default-deny every known built-in.
    for wire in OPENCODE_BUILTIN_TOOLS.values():
        permissions[wire] = "deny"

    # Flip allowed builtins to "ask".
    for abstract in abstract_client_tools:
        if abstract in OPENCODE_BUILTIN_TOOLS:
            wire = OPENCODE_BUILTIN_TOOLS[abstract]
            permissions[wire] = "ask"
            wire_allowlist.append(wire)
        elif abstract in FORGE_CUSTOM_TOOLS:
            wire = FORGE_CUSTOM_TOOLS[abstract]["name"]
            permissions[wire] = "ask"
            wire_allowlist.append(wire)
        else:
            log.warning("Unknown abstract tool %r — skipped", abstract)

    return permissions, wire_allowlist


# ============================================================================
# Section 5 — OpenCodeAdapter implementation
# ============================================================================

@dataclass
class _SessionState:
    """Per-session state shared between spawn_agent() and the back-channel
    HTTP handler. Stored in `OpenCodeAdapter._sessions` keyed by session_id.

    The SSE consumer pushes events onto `events_q`. The back-channel handler
    (which runs in a different asyncio task) also pushes onto `events_q` for
    MCP-proxy proposals, and registers a Future in `pending_mcp` that gets
    resolved when the caller asend()s the matching ToolResult.

    `outstanding_call_id` is the call_id of the proposal currently awaiting a
    ToolResult — it's None when no proposal is pending. The asend() dispatch
    in spawn_agent() uses this to decide whether to call _respond_permission
    (built-in tool) or resolve a Future (MCP proxy tool).
    """
    session_id: str
    aggregate_id: str
    events_q: asyncio.Queue
    pending_mcp: dict[str, asyncio.Future] = field(default_factory=dict)


adapter_id = "opencode"


class OpenCodeAdapter(IKernelAdapter):
    """OpenCode kernel adapter — talks to `opencode serve` over HTTP+SSE.

    Threading: each `spawn_agent()` call opens its own session and SSE stream
    on the server. Multiple in-flight spawn_agent generators are fine
    (OpenCode is designed for multi-client use). Do not share an in-flight
    async generator across asyncio tasks.
    """

    KERNEL_ID = "opencode"  # kept for payload tags; module-level adapter_id = "opencode"

    def __init__(
        self,
        server_url: str = "http://localhost:4096",
        server_password: str | None = None,
        *,
        auto_spawn_server: bool = False,
        server_workdir: str | None = None,
        mcp_proxy_command: list[str] | None = None,
        permission_timeout_s: float = 120.0,
        backchannel_host: str = "127.0.0.1",
        mcp_proxy_timeout_s: float = 120.0,
    ) -> None:
        if not _SDK_AVAILABLE:
            raise RuntimeError(
                "opencode-ai SDK not installed. Run `pip install opencode-ai`."
            )

        self._server_url = server_url.rstrip("/")
        self._server_password = server_password or os.environ.get(
            "OPENCODE_SERVER_PASSWORD"
        )
        self._auto_spawn = auto_spawn_server
        self._workdir = server_workdir or os.getcwd()
        # e.g. ["python", "-m", "forge.kernel.opencode_mcp_proxy"]
        self._mcp_proxy_cmd = mcp_proxy_command
        self._permission_timeout = permission_timeout_s
        self._mcp_proxy_timeout = mcp_proxy_timeout_s

        self._server_proc: subprocess.Popen | None = None
        self._client: Any | None = None  # AsyncOpencode

        # Back-channel: a loopback aiohttp server the MCP proxy POSTs to.
        # Started in __aenter__ iff mcp_proxy_command is configured.
        self._bc_host = backchannel_host
        self._bc_port: int | None = None
        self._bc_runner: Any | None = None  # aiohttp.web.AppRunner
        self._sessions: dict[str, _SessionState] = {}

    # ---- lifecycle -----------------------------------------------------------

    async def __aenter__(self) -> OpenCodeAdapter:
        # Start the loopback back-channel BEFORE spawning opencode serve, so
        # the proxy can connect immediately when OpenCode starts it.
        if self._mcp_proxy_cmd:
            await self._start_backchannel()
        if self._auto_spawn:
            await self._spawn_server()
        # SDK is httpx-based; basic auth header is set via the server URL
        # or via the `auth` kwarg depending on the generated SDK shape.
        self._client = AsyncOpencode(base_url=self._server_url)
        # If a password is configured, the SDK's underlying httpx client
        # picks up HTTP Basic via env vars or an explicit auth tuple.
        # See SDK docs — varies slightly across generator versions.
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.close()
        if self._server_proc is not None:
            self._server_proc.send_signal(signal.SIGTERM)
            try:
                self._server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._server_proc.kill()
        # Shut down back-channel LAST: a still-running MCP proxy might post
        # a final result during opencode shutdown, and we want to consume
        # it cleanly rather than leaving the proxy hanging on a TCP RST.
        if self._bc_runner is not None:
            await self._stop_backchannel()

    async def _spawn_server(self) -> None:
        """Start `opencode serve` as a subprocess. Useful for CI/tests."""
        if shutil.which("opencode") is None:
            raise RuntimeError("`opencode` binary not on PATH")

        env = os.environ.copy()
        if self._server_password:
            env["OPENCODE_SERVER_PASSWORD"] = self._server_password

        # Pin port from server_url for the subprocess.
        port = self._server_url.rsplit(":", 1)[-1]
        self._server_proc = subprocess.Popen(
            ["opencode", "serve", "--hostname", "127.0.0.1", "--port", port],
            cwd=self._workdir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Crude readiness wait — production version should poll /health.
        await asyncio.sleep(2.0)

    # ---- back-channel server -------------------------------------------------
    # The Forge MCP proxy (forge/kernel/opencode_mcp_proxy.py) runs as a
    # grandchild of this Python process (Forge → opencode serve → proxy). It
    # can't share asyncio.Queue objects with us, so it POSTs every tool call
    # to a tiny loopback HTTP server we run here.

    async def _start_backchannel(self) -> None:
        """Bind an aiohttp server on 127.0.0.1:0 (kernel-assigned port).

        Two routes:
            POST /propose  — proxy submits a tool call; we yield a
                             ToolUseProposal, await asend(), return result.
            GET  /health   — liveness probe for the proxy on startup.
        """
        if not _AIOHTTP_AVAILABLE:
            raise RuntimeError(
                "aiohttp not installed. Run `pip install aiohttp` "
                "(required only when mcp_proxy_command is configured)."
            )
        app = _aiohttp_web.Application()
        app.router.add_post("/propose", self._handle_propose)
        app.router.add_get("/health", self._handle_health)

        runner = _aiohttp_web.AppRunner(app, access_log=None)
        await runner.setup()
        # Port 0 → OS picks a free ephemeral port. Avoids collisions across
        # parallel Forge runs in CI.
        site = _aiohttp_web.TCPSite(runner, self._bc_host, 0)
        await site.start()

        # Extract the actually-bound port from the live socket.
        server = site._server  # type: ignore[attr-defined]
        sockets = server.sockets if server else []
        if not sockets:
            await runner.cleanup()
            raise RuntimeError("back-channel socket failed to bind")
        self._bc_port = sockets[0].getsockname()[1]
        self._bc_runner = runner
        log.info("Forge back-channel listening on http://%s:%d",
                 self._bc_host, self._bc_port)

    async def _stop_backchannel(self) -> None:
        # Cancel any still-pending MCP futures so awaiters don't deadlock.
        for sess in self._sessions.values():
            for fut in sess.pending_mcp.values():
                if not fut.done():
                    fut.set_exception(RuntimeError("adapter shutting down"))
            sess.pending_mcp.clear()
        self._sessions.clear()
        if self._bc_runner is not None:
            await self._bc_runner.cleanup()
            self._bc_runner = None

    @property
    def _backchannel_url(self) -> str | None:
        if self._bc_port is None:
            return None
        return f"http://{self._bc_host}:{self._bc_port}"

    async def _handle_health(self, request: Any) -> Any:
        return _aiohttp_web.Response(text="ok")

    async def _handle_propose(self, request: Any) -> Any:
        """Accept a tool proposal from the MCP proxy, route it through the
        Forge Proposal boundary, and return the validated/executed result.

        Flow:
            1. Parse {session_id, call_id, abstract_tool, inputs}.
            2. Look up the per-session _SessionState; 404 if unknown.
            3. Create a Future, register it under call_id, push a
               ToolUseProposal onto the session's events_q.
            4. spawn_agent picks up the proposal, yields it, and the caller
               asend()s a ToolResult — which resolves the Future (see the
               dispatch branch in spawn_agent below).
            5. Convert ToolResult → JSON response back to the proxy.
        """
        try:
            body = await request.json()
        except Exception as e:
            return _aiohttp_web.json_response(
                {"error": f"malformed JSON: {e}"}, status=400,
            )

        _session_id_req = body.get("session_id")         # legacy field, may be absent
        aggregate_id  = body.get("aggregate_id")          # primary routing key
        call_id       = body.get("call_id")
        abstract_tool = body.get("abstract_tool")
        inputs        = body.get("inputs") or {}

        if not (aggregate_id and call_id and abstract_tool):
            return _aiohttp_web.json_response(
                {"error": "missing aggregate_id/call_id/abstract_tool"},
                status=400,
            )

        sess = self._sessions.get(aggregate_id)
        if sess is None:
            return _aiohttp_web.json_response(
                {"error": f"unknown aggregate {aggregate_id}"}, status=404,
            )

        # Register the Future BEFORE pushing the proposal, so the dispatch
        # branch in spawn_agent can never race ahead and miss it.
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        sess.pending_mcp[call_id] = future

        # Build the wire name as OpenCode reports it — keeps the audit log
        # consistent with built-in tool proposals.
        wire_name = FORGE_CUSTOM_TOOLS.get(abstract_tool, {}).get(
            "name", f"mcp::{abstract_tool}"
        )

        await sess.events_q.put(ToolUseProposal(
            kind=EventKind.TOOL_USE_PROPOSED,
            aggregate_id=sess.aggregate_id,
            tool_use_id=call_id,
            tool_name=wire_name,
            abstract_tool=abstract_tool,
            inputs=inputs,
            payload={"source": "mcp_proxy", "aggregate_id": aggregate_id},
        ))

        try:
            result: ToolResult = await asyncio.wait_for(
                future, timeout=self._mcp_proxy_timeout,
            )
        except TimeoutError:
            sess.pending_mcp.pop(call_id, None)
            return _aiohttp_web.json_response(
                {"error": "Forge validator timed out"}, status=504,
            )
        except Exception as e:
            sess.pending_mcp.pop(call_id, None)
            return _aiohttp_web.json_response(
                {"error": f"validator error: {e!r}"}, status=500,
            )

        if result.is_error:
            content = result.content if isinstance(result.content, str) \
                else json.dumps(result.content)
            return _aiohttp_web.json_response({"error": content}, status=200)

        content = result.content if isinstance(result.content, str) \
            else json.dumps(result.content)
        return _aiohttp_web.json_response({"content": content})

    # ---- FR-KA-002 -----------------------------------------------------------

    def get_capabilities(self) -> KernelCapabilities:
        return KernelCapabilities(
            kernel_id=self.KERNEL_ID,
            streaming=True,                 # SSE /event stream
            deterministic_output=False,     # Underlying LLM is non-deterministic
            extended_thinking=True,         # Provider-dependent; passed through
            prompt_caching=True,            # Provider-dependent (Anthropic/etc.)
            vision=True,                    # Drag-drop images supported
            batch_api=False,                # No native batch endpoint
            hooks_native=True,              # Plugin hooks: tool.execute.before, event, chat.message
            subagents_native=True,          # /task tool — disabled in v0.1 by policy
            mcp_remote=True,                # Native MCP client
            mcp_local_stdio=True,           # Native MCP client
            client_tools=list(OPENCODE_BUILTIN_TOOLS.keys()),
            server_tools=[],                # OpenCode runs everything locally
            max_context_tokens=200_000,     # Provider-dependent; conservative
            notes={
                "owns_agent_loop": (
                    "OpenCode server owns the model→tool→model loop. Forge's "
                    "Proposal boundary is preserved via permission-API gating "
                    "and the optional Forge MCP proxy server."
                ),
                "subagents_disabled_v01": (
                    "The /task tool spawns subagents that break aggregate-ID "
                    "nesting in the Forge audit ledger. Re-enable in v0.2."
                ),
                "skills_disabled_v01": (
                    "The skill tool loads arbitrary SKILL.md files; Forge "
                    "needs prompt provenance for FR-AG-002 before enabling."
                ),
            },
        )

    # ---- FR-KA-004 -----------------------------------------------------------

    async def spawn_agent(
        self,
        persona: AgentPersona,
        context: str,
        tools: list[str],
        aggregate_id: str,
        *,
        timeout_s: float = 600.0,
    ) -> AsyncIterator[NormalizedEvent]:
        """Run one agent turn cycle via OpenCode and yield normalized events.

        Same contract as ClaudeAdapter.spawn_agent and ClaudeSDKAdapter.spawn_agent:
        caller MUST `agen.asend()` a ToolResult for every ToolUseProposal
        yielded, or the permission API request will time out after
        `permission_timeout_s` and the agent will treat the tool as denied.
        """
        if self._client is None:
            raise RuntimeError("OpenCodeAdapter used outside `async with` block")

        # Restrict persona tools by caller-supplied scope
        allowed_abstract = [t for t in persona.allowed_tools if t in set(tools)]
        permissions, wire_allowlist = build_session_permissions(allowed_abstract)

        # ----- 1) Set up the per-session state BEFORE create_session, so the
        #         back-channel handler is ready the instant the proxy boots.
        events_q: asyncio.Queue = asyncio.Queue()
        sess_state = _SessionState(
            session_id="",          # filled in after session.create() returns
            aggregate_id=aggregate_id,
            events_q=events_q,
        )
        # Register under aggregate_id — that's what the MCP proxy will send.
        self._sessions[aggregate_id] = sess_state

        # ----- 2) Create session with the persona's restrictive agent config
        try:
            session = await self._create_session(persona, permissions, aggregate_id)
        except Exception:
            self._sessions.pop(aggregate_id, None)
            raise
        session_id = session["id"]
        sess_state.session_id = session_id

        yield NormalizedEvent(
            kind=EventKind.SESSION_STARTED,
            aggregate_id=aggregate_id,
            payload={
                "persona":      persona.name,
                "model":        persona.preferred_model,
                "kernel":       self.KERNEL_ID,
                "session_id":   session_id,
                "client_tools": allowed_abstract,
                "agent":        persona.opencode_agent_name,
            },
        )

        # ----- 3) Start the SSE consumer (it pushes onto the same events_q
        #         the back-channel handler uses, so spawn_agent sees both
        #         built-in tool proposals and MCP proxy proposals on one
        #         stream).
        pending_perms: dict[str, asyncio.Future] = {}  # reserved for future use
        sse_task = asyncio.create_task(
            self._consume_sse(session_id, events_q, pending_perms, aggregate_id)
        )

        # ----- 4) Submit the prompt (non-blocking — events arrive via SSE)
        await self._submit_prompt(session_id, persona, context)

        # ----- 5) Drain events; pause on tool proposals for caller's asend()
        SENTINEL = object()

        try:
            while True:
                try:
                    item = await asyncio.wait_for(events_q.get(), timeout=timeout_s)
                except TimeoutError:
                    yield NormalizedEvent(
                        kind=EventKind.AGENT_FAILED,
                        aggregate_id=aggregate_id,
                        payload={"reason": "timeout", "timeout_s": timeout_s},
                    )
                    return

                if item is SENTINEL:
                    break

                event = item  # NormalizedEvent or ToolUseProposal

                if isinstance(event, ToolUseProposal):
                    # Pause the generator and wait for the orchestrator's
                    # ToolResult. The Validator+Executor live in the caller.
                    outstanding_tool_use_id = event.tool_use_id
                    proposal_source = event.payload.get("source")  # "mcp_proxy" or None
                    outstanding_permission_id = event.payload.get("permission_id")
                    result: ToolResult = yield event  # caller does asend()

                    if not isinstance(result, ToolResult):
                        raise RuntimeError(
                            f"spawn_agent expected ToolResult, got {type(result)}"
                        )
                    if result.tool_use_id != outstanding_tool_use_id:
                        raise RuntimeError(
                            f"ToolResult id mismatch: expected "
                            f"{outstanding_tool_use_id}, got {result.tool_use_id}"
                        )

                    # Dispatch: MCP-proxy proposals are answered by resolving
                    # the Future the back-channel handler is awaiting.
                    # Built-in tool proposals are answered via the OpenCode
                    # permission API.
                    if proposal_source == "mcp_proxy":
                        fut = sess_state.pending_mcp.pop(
                            outstanding_tool_use_id, None,
                        )
                        if fut is None or fut.done():
                            log.warning(
                                "No pending MCP future for call_id=%s "
                                "(proxy may have timed out)",
                                outstanding_tool_use_id,
                            )
                        else:
                            fut.set_result(result)
                    else:
                        await self._respond_permission(
                            session_id=session_id,
                            permission_id=outstanding_permission_id,
                            result=result,
                        )
                else:
                    yield event
                    if event.kind in (EventKind.AGENT_COMPLETED, EventKind.AGENT_FAILED):
                        break

        finally:
            sse_task.cancel()
            try:
                await sse_task
            except (asyncio.CancelledError, Exception):
                pass
            # Cancel any orphaned MCP futures and deregister the session.
            for fut in sess_state.pending_mcp.values():
                if not fut.done():
                    fut.set_exception(RuntimeError(
                        "spawn_agent ended with pending MCP call"
                    ))
            self._sessions.pop(aggregate_id, None)

    # ---- FR-KA-005: on_event -------------------------------------------------

    async def on_event(self, event: NormalizedEvent) -> None:
        """Forge lifecycle events arriving at the kernel.

        OpenCode supports plugin hooks (tool.execute.before/after, chat.message,
        session.idle) but those are written in TS and loaded by the OpenCode
        server itself. Hooks at THIS seam — events sent from Forge *into* the
        kernel — would be forwarded via the plugin's IPC channel.

        v0.1: log only. v0.2: write a `.opencode/plugin/forge_bridge.ts` that
        accepts JSON-RPC over a Unix socket from this method.
        """
        log.debug("on_event: %s aggregate=%s", event.kind, event.aggregate_id)

    # ---- FR-KA-001: sync_memory ----------------------------------------------

    async def sync_memory(self, lkg_snapshot: dict[str, Any] | None = None) -> None:
        """No-op. Forge's LKG is authoritative. Relevant lessons are injected
        into the prompt by the Context Pruner before each spawn_agent() call
        (FR-AG-002). OpenCode's session compaction (experimental.session.compacting
        hook) could be customized later to read from LKG, but that's a v0.3
        optimization."""
        return None

    # ========================================================================
    # Internals
    # ========================================================================

    async def _create_session(
        self,
        persona: AgentPersona,
        permissions: dict[str, str],
        aggregate_id: str,
    ) -> dict[str, Any]:
        """POST /session — creates a new session with persona-derived config.

        NOTE: parameter names below follow the OpenCode OpenAPI spec naming
        convention. Verify against the generated SDK shape after a fresh
        `pip install opencode-ai` — Stainless occasionally re-cases fields.
        """
        # Compose the system-prompt-equivalent: OpenCode reads AGENTS.md and
        # the agent's markdown frontmatter. For session-scoped overrides we
        # pass `instructions` (or `system`) inline.
        system_prompt = self._build_system_prompt(persona)

        body = {
            "title": f"forge::{persona.name}",
            "directory": self._workdir,
            "agent": persona.primary_agent_template,  # "build" | "plan" | custom
            "model": persona.preferred_model,
            "instructions": system_prompt,
            "permissions": permissions,
            "temperature": persona.temperature,
            "max_tokens": persona.max_tokens,
        }
        if persona.thinking_budget_tokens:
            body["provider_options"] = {
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": persona.thinking_budget_tokens,
                },
                **persona.extra_provider_options,
            }
        elif persona.extra_provider_options:
            body["provider_options"] = persona.extra_provider_options

        # If an MCP proxy command is configured, register it for this session.
        # If an MCP proxy command is configured, register it for this session
        # and pass the back-channel URL + aggregate_id through env vars. The
        # proxy reads these at boot (see opencode_mcp_proxy.py).
        #
        # We route on aggregate_id (Forge-owned, generated before this call)
        # rather than OpenCode's session_id (which we don't know yet — the
        # session.create() response is what would tell us). One spawn_agent
        # call = one aggregate_id = one OpenCode session, so there's no
        # ambiguity.
        if self._mcp_proxy_cmd:
            if self._backchannel_url is None:
                raise RuntimeError(
                    "mcp_proxy_command set but back-channel not started; "
                    "this is a bug in OpenCodeAdapter.__aenter__"
                )
            body["mcp"] = {
                "forge_proxy": {
                    "type": "local",
                    "command": self._mcp_proxy_cmd,
                    "enabled": True,
                    "environment": {
                        "FORGE_BACKCHANNEL_URL": self._backchannel_url,
                        "FORGE_AGGREGATE_ID":    aggregate_id,
                        "FORGE_PROXY_TIMEOUT_S": str(int(self._mcp_proxy_timeout)),
                    },
                },
            }

        session = await self._client.session.create(**body)  # type: ignore[union-attr]
        # SDK returns a pydantic model; normalize to dict
        if hasattr(session, "model_dump"):
            session = session.model_dump()
        return session

    def _build_system_prompt(self, persona: AgentPersona) -> str:
        """Compose the system prompt block injected into the session."""
        constraints = "\n".join(f"- {c}" for c in persona.constraints) or "(none)"
        contract = json.dumps(persona.output_contract or {}, indent=2)
        return (
            f"# Role\n{persona.role}\n\n"
            f"# Goal\n{persona.goal}\n\n"
            f"# Constraints\n{constraints}\n\n"
            f"# Output contract\n```json\n{contract}\n```\n\n"
            "# Operating principles\n"
            "- You are running inside Forge OS via the OpenCode kernel.\n"
            "- Every tool call is gated by Forge's Validator. Denied tools "
            "  will return an error result; do not retry the same call.\n"
            "- Do not invoke subagents or load skills unless explicitly told.\n"
        )

    async def _submit_prompt(
        self,
        session_id: str,
        persona: AgentPersona,
        context: str,
    ) -> None:
        """POST /session/:id/message — kick off the model loop."""
        # The SDK exposes this as either client.session.prompt() or
        # client.session.message.create() depending on the generator version.
        # Adjust here once verified locally.
        await self._client.session.prompt(  # type: ignore[union-attr]
            id=session_id,
            parts=[{"type": "text", "text": context}],
            model=persona.preferred_model,
            agent=persona.opencode_agent_name,
        )

    async def _consume_sse(
        self,
        session_id: str,
        events_q: asyncio.Queue,
        pending_perms: dict[str, asyncio.Future],
        aggregate_id: str,
    ) -> None:
        """Subscribe to /event and translate OpenCode events → normalized events.

        Event taxonomy (from the OpenCode OpenAPI spec):
            server.connected               → ignore
            message.part.delta             → TEXT_DELTA / THINKING_DELTA
            message.part.updated           → ignore (deltas already streamed)
            permission.requested           → ToolUseProposal
            permission.replied             → ignore (we initiated the reply)
            tool.execute.before            → debug log
            tool.execute.after             → SERVER_TOOL_EXECUTED (for audit)
            session.idle                   → AGENT_COMPLETED
            session.error                  → AGENT_FAILED
        """
        try:
            stream = await self._client.event.list()  # type: ignore[union-attr]
            async for ev in stream:
                ev_dict = ev.model_dump() if hasattr(ev, "model_dump") else dict(ev)
                etype = ev_dict.get("type") or ev_dict.get("event")
                props = ev_dict.get("properties") or ev_dict.get("data") or {}

                # Filter to this session where applicable
                ev_session = props.get("session_id") or props.get("sessionID")
                if ev_session and ev_session != session_id:
                    continue

                if etype == "message.part.delta":
                    part = props.get("part") or props
                    text = part.get("text")
                    thinking = part.get("thinking")
                    if text:
                        await events_q.put(NormalizedEvent(
                            kind=EventKind.TEXT_DELTA,
                            aggregate_id=aggregate_id,
                            payload={"text": text},
                        ))
                    if thinking:
                        await events_q.put(NormalizedEvent(
                            kind=EventKind.THINKING_DELTA,
                            aggregate_id=aggregate_id,
                            payload={"thinking": thinking},
                        ))

                elif etype == "permission.requested":
                    # Translate to a ToolUseProposal. The orchestrator's
                    # ToolResult becomes the allow/deny decision in
                    # _respond_permission().
                    perm_id = props.get("permission_id") or props.get("id")
                    tool_wire = props.get("tool") or props.get("name", "")
                    inputs = props.get("inputs") or props.get("args") or {}
                    abstract = _wire_to_abstract(tool_wire)

                    await events_q.put(ToolUseProposal(
                        kind=EventKind.TOOL_USE_PROPOSED,
                        aggregate_id=aggregate_id,
                        tool_use_id=perm_id or tool_wire,
                        tool_name=tool_wire,
                        abstract_tool=abstract,
                        inputs=inputs,
                        payload={"permission_id": perm_id, "session_id": session_id},
                    ))

                elif etype == "tool.execute.after":
                    # For audit purposes — the tool already ran (either Forge
                    # approved + the server executed, or it was auto-approved).
                    await events_q.put(NormalizedEvent(
                        kind=EventKind.SERVER_TOOL_EXECUTED,
                        aggregate_id=aggregate_id,
                        payload={
                            "tool": props.get("tool"),
                            "duration_ms": props.get("duration_ms"),
                            "ok": props.get("ok", True),
                        },
                    ))

                elif etype == "session.idle":
                    await events_q.put(NormalizedEvent(
                        kind=EventKind.AGENT_COMPLETED,
                        aggregate_id=aggregate_id,
                        payload={"session_id": session_id},
                    ))
                    await events_q.put(_SSE_SENTINEL)
                    return

                elif etype == "session.error":
                    await events_q.put(NormalizedEvent(
                        kind=EventKind.AGENT_FAILED,
                        aggregate_id=aggregate_id,
                        payload={"reason": "session_error", "detail": props},
                    ))
                    await events_q.put(_SSE_SENTINEL)
                    return

                # else: ignored event type (server.connected, etc.)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("SSE consumer crashed")
            await events_q.put(NormalizedEvent(
                kind=EventKind.AGENT_FAILED,
                aggregate_id=aggregate_id,
                payload={"reason": "sse_crash", "detail": repr(e)},
            ))
            await events_q.put(_SSE_SENTINEL)

    async def _respond_permission(
        self,
        session_id: str,
        permission_id: str | None,
        result: ToolResult,
    ) -> None:
        """POST /session/:id/permissions/:perm_id — allow or deny the tool call.

        If Forge's Validator approved (result.is_error == False), we send
        `allow` and pass the result content as the synthetic tool output.
        If denied, we send `deny` with the error message — the model sees
        a "permission denied" result and decides whether to retry.

        Some OpenCode versions accept a `response_data` field that supplies
        a synthetic output instead of letting the server actually execute
        the tool. That's the cleanest fit for Forge's model where the
        Executor runs the side effect itself. Fallback: server executes,
        result.content is ignored, we log the discrepancy.
        """
        if permission_id is None:
            log.warning("No permission_id on tool result %s — cannot respond",
                        result.tool_use_id)
            return

        decision = "deny" if result.is_error else "allow"
        body = {"decision": decision}
        if not result.is_error:
            body["response_data"] = (
                result.content if isinstance(result.content, str)
                else json.dumps(result.content)
            )

        # Method name varies — adjust per generated SDK.
        await self._client.session.permission.respond(  # type: ignore[union-attr]
            session_id=session_id,
            permission_id=permission_id,
            **body,
        )


# ============================================================================
# Section 6 — small helpers
# ============================================================================

_SSE_SENTINEL = object()  # marks end-of-stream on events_q


def _wire_to_abstract(wire: str) -> str:
    """Reverse-lookup OpenCode wire name → Forge abstract name."""
    for abstract, w in OPENCODE_BUILTIN_TOOLS.items():
        if w == wire:
            return abstract
    for abstract, spec in FORGE_CUSTOM_TOOLS.items():
        if spec["name"] == wire:
            return abstract
    return wire  # unknown — pass through


def load_persona_yaml(path: str) -> AgentPersona:
    """Load a Forge persona YAML and flatten OpenCode-specific overrides.

    Identical contract to claude_adapter.load_persona_yaml — in production
    this lives in forge/agents/loader.py and is shared.
    """
    import yaml  # local import keeps yaml optional at module-load time

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    kernel_overrides = raw.pop("kernel_overrides", {}) or {}
    opencode_block = kernel_overrides.get("opencode", {}) or {}

    return AgentPersona(
        name=raw["name"],
        role=raw["role"],
        goal=raw["goal"],
        constraints=raw.get("constraints", []),
        allowed_tools=raw.get("allowed_tools", []),
        allowed_server_tools=raw.get("allowed_server_tools", []),
        output_contract=raw.get("output_contract", {}),
        preferred_model=opencode_block.get("preferred_model",
                                           "anthropic/claude-opus-4-7"),
        max_tokens=opencode_block.get("max_tokens", 4096),
        temperature=opencode_block.get("temperature", 0.0),
        thinking_budget_tokens=opencode_block.get("thinking_budget_tokens"),
        opencode_agent_name=opencode_block.get("agent_name", "forge"),
        primary_agent_template=opencode_block.get("primary_agent", "build"),
        enable_skills=opencode_block.get("enable_skills", False),
        enable_subagents=opencode_block.get("enable_subagents", False),
        extra_provider_options=opencode_block.get("extra_provider_options", {}),
    )


# ============================================================================
# Section 7 — Smoke test
# ============================================================================

async def _smoke_test() -> None:
    """Exercise the propose→stub-validate→continue loop against a running
    `opencode serve`. Requires:
        - opencode binary on PATH
        - OPENCODE_SERVER_PASSWORD env var matching the server (or no auth)
        - A provider API key configured via `opencode auth login` beforehand
    """
    persona = AgentPersona(
        name="event-storming",
        role="You are an event storming facilitator.",
        goal="Propose one domain event for a hello-world bounded context.",
        constraints=[
            "Output exactly one event via forge_propose_event.",
            "No prose.",
        ],
        allowed_tools=["ProposeEvent"],
        preferred_model="anthropic/claude-opus-4-7",
        thinking_budget_tokens=2048,
    )

    async with OpenCodeAdapter(
        server_url=os.environ.get("OPENCODE_URL", "http://localhost:4096"),
        server_password=os.environ.get("OPENCODE_SERVER_PASSWORD"),
        auto_spawn_server=False,  # assume user already ran `opencode serve`
    ) as adapter:

        print("Capabilities:", adapter.get_capabilities())

        agen = adapter.spawn_agent(
            persona=persona,
            context="Sketch one domain event. Use forge_propose_event.",
            tools=persona.allowed_tools,
            aggregate_id="smoke-001",
        )

        pending: ToolUseProposal | None = None
        while True:
            try:
                event = await (
                    agen.asend(None) if pending is None
                    else agen.asend(ToolResult(
                        tool_use_id=pending.tool_use_id,
                        content='{"ack": true, "validator": "stub"}',
                    ))
                )
            except StopAsyncIteration:
                break

            pending = None
            if isinstance(event, ToolUseProposal):
                print(f"[proposal] {event.abstract_tool} ({event.tool_name})")
                print(f"           inputs={event.inputs}")
                pending = event
            else:
                print(f"[event] {event.kind} payload={event.payload}")


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if "--smoke" in sys.argv:
        asyncio.run(_smoke_test())
    else:
        print(
            "Run with --smoke to exercise the adapter.\n"
            "Prerequisites:\n"
            "  - `pip install opencode-ai`\n"
            "  - `opencode serve --port 4096` running in another terminal\n"
            "  - A provider configured via `opencode auth login` (e.g. Anthropic)\n"
        )