"""
forge.kernel.codex
==================

Reference implementation of the Forge OS Kernel Adapter for **OpenAI Codex**,
built on top of the `codex app-server` JSON-RPC protocol.

This is the fifth kernel adapter, parallel to:

    claude_adapter.py      -> anthropic.AsyncAnthropic.messages.create()
    claude_sdk_adapter.py  -> claude_agent_sdk.ClaudeSDKClient
    opencode_adapter.py    -> opencode_ai.AsyncOpencode -> `opencode serve` (HTTP+SSE)
    human_adapter.py       -> a person at a terminal
    codex_adapter.py       -> `codex app-server`            (THIS FILE)

The interfaces, normalized events, and Proposal-boundary semantics are
**identical** to the other adapters. The only thing that changes is what runs
the agent loop: a managed `codex app-server` subprocess, driven over
newline-delimited JSON-RPC 2.0 on stdio.

Why Codex is wired over `app-server` and not the SDK or `codex exec`
-------------------------------------------------------------------
Codex exposes three programmatic surfaces:

  1. `codex exec --json`  — one-shot headless run, JSONL events. This is what
     the official **TypeScript** SDK (`@openai/codex-sdk`) wraps. There is no
     Python SDK, and `exec` runs a turn to completion without a structured
     approval round-trip — you cannot pause it mid-tool-call and hand the
     proposed action to Forge's Validator.
  2. `@openai/codex-sdk`  — TypeScript/Node only. Wrong language for Forge, and
     it's just a thin wrapper over `codex exec` anyway.
  3. `codex app-server`   — the bidirectional JSON-RPC 2.0 protocol that powers
     the Codex IDE extension. It streams item/turn events AND issues
     *server-initiated approval requests* before Codex runs a command or
     applies a file edit. THIS is the surface a kernel-agnostic orchestrator
     wants, because the approval request is a natural Proposal boundary.

So, exactly as the Claude *SDK* adapter chose a different substrate from the
raw Claude adapter, the Codex adapter chooses `app-server` over `exec`: the
protocol gives us a real proposal/decision handshake instead of a fire-and-
forget run.

The key design decision: approval-as-Proposal (and the execution boundary)
--------------------------------------------------------------------------
Codex was designed around an *external approver*. When `approvalPolicy` is not
`"never"`, Codex emits a server request before each side-effecting action:

    item/commandExecution/requestApproval   (shell / apply_patch via shell)
    item/fileChange/requestApproval         (apply_patch file edits)

and blocks until the client answers `accept | acceptForSession | decline |
cancel`. Forge simply *is* that client. Every command and every edit therefore
passes through Forge's Validator before it can happen — that's the Proposal
boundary (§2.7 Bounded Autonomy), expressed natively by the protocol. None of
the other four kernels gives you this for free; the Claude SDK and OpenCode
adapters had to *manufacture* the boundary by disabling built-ins and proxying
tools through MCP.

But "Forge has veto power over each action" is not the same as "Forge executes
each action." There are two coherent modes, and this adapter supports both via
`execution_boundary`:

  * execution_boundary="kernel"  (DEFAULT, fully wired here)
        sandbox=workspaceWrite, approvalPolicy=unlessTrusted.
        Codex proposes -> Forge's Validator decides accept/decline -> on accept,
        *Codex's own sandbox executes* the command/edit. Forge owns the
        decision, not the execution. Accepted built-in actions are tagged
        `kernel_executed` in the Audit Ledger (§3.34) — the SAME category the
        Claude adapter already uses for Anthropic server tools (web_search,
        code_execution) that run on the kernel side. Codex's reviewer, plan
        updates, and reasoning all run as designed. This is the mode that
        actually exercises Codex as a coding agent and gives the truest
        kernel-vs-kernel latency/quality comparison.

  * execution_boundary="forge"   (design wired, MCP back-channel is the
        integration point — see Section 7)
        sandbox=readOnly so Codex's built-in shell/apply_patch CANNOT mutate
        anything, and Forge's abstract tools (Write, Edit, Bash, ProposeEvent,
        ReadLKG) are exposed to Codex as MCP tools. The model is then forced to
        route every mutation through Forge's Executor — identical semantics to
        the OpenCode adapter (`readOnly` + MCP proxy + loopback back-channel).
        Use this when you need byte-for-byte the same execution path across all
        kernels and are willing to fight the model's preference for apply_patch.

Design invariants (identical to the other adapters)
---------------------------------------------------
1. The adapter is *dumb* about policy. It does NOT decide whether a tool may
   run. It yields a ToolUseProposal and pauses; the orchestrator runs the
   proposal through Forge's Validator + Executor and feeds a ToolResult back via
   the async generator's `asend()` method.
2. The adapter does not mutate Forge state. All state changes go through the
   Proposal boundary as events.
3. The adapter does not own memory. Forge's LKG is the authoritative store;
   `sync_memory()` is intentionally a no-op for MVP.
4. Kernel-side execution (built-in apply_patch/shell in "kernel" mode, plus the
   `web_search` tool) bypasses Forge's Executor. The adapter emits events
   flagged for the Audit Ledger so they're tagged `kernel_executed`.

Dependencies
------------
    # Python: stdlib only (asyncio, json, subprocess). No pip install needed.
    # External runtime:
    #   - `codex` binary on PATH (npm i -g @openai/codex, or the installer)
    #   - Auth: `codex login` (ChatGPT account) OR CODEX_API_KEY / OPENAI_API_KEY
    #           in the environment for headless use.
    # Optional (execution_boundary="forge"): the shared forge_mcp_proxy.py
    #   built for the OpenCode adapter, reused verbatim.

Protocol notes / version sensitivity
-------------------------------------
The app-server schema is versioned with the Codex binary. Generate the exact
schema you're targeting with:

    codex app-server generate-json-schema --out ./schemas
    codex app-server generate-ts --out ./schemas

A few field names below (notably the approval-decision response shape) are
marked VERIFY — confirm them against your installed Codex's generated schema
before relying on them in production. They are isolated in `_approval_response`
so there's exactly one place to fix.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from forge_os.kernel.types import (
    AgentPersona,
    EventKind,
    IKernelAdapter,
    KernelCapabilities,
    NormalizedEvent,
    ToolResult,
    ToolUseProposal,
)

log = logging.getLogger("forge.kernel.codex")


adapter_id = "codex"


# ============================================================================
# Section 2 — Abstract-tool mapping
# ============================================================================
# Forge speaks in abstract tool names; Codex speaks in commandExecution /
# fileChange items and (in forge-mode) MCP tools. This is the translation the
# Capability Manager (FR-KA-002) and the Audit Ledger care about.

def _abstract_tool_for_approval(method: str, params: dict[str, Any]) -> str:
    """Map a Codex approval request to a Forge abstract tool name."""
    if method.startswith("item/fileChange"):
        # A proposed apply_patch edit. Forge treats create/modify as Write,
        # in-place edits as Edit; we can't always tell, so default to Write.
        changes = params.get("changes") or []
        kinds = {c.get("kind") for c in changes if isinstance(c, dict)}
        if kinds and kinds.issubset({"update", "modify", "edit"}):
            return "Edit"
        return "Write"
    if method.startswith("item/commandExecution"):
        # Network-access approvals piggyback on the command channel.
        if params.get("networkApprovalContext"):
            return "NetworkAccess"
        return "Bash"
    # Dynamic / MCP tool call routed to the client.
    return params.get("tool") or params.get("abstract_tool") or "UnknownTool"


# ============================================================================
# Section 3 — JSON-RPC over stdio transport
# ============================================================================

@dataclass
class _Pending:
    future: asyncio.Future[dict[str, Any]]


class _AppServerClient:
    """A thin async JSON-RPC 2.0 client over a `codex app-server` subprocess.

    Wire format: one JSON object per line on stdin/stdout. The `"jsonrpc":"2.0"`
    header is omitted (app-server convention). Three kinds of inbound message:

        response       -> has `id` + (`result` | `error`), no `method`
        server request -> has `id` + `method`           (approvals, dynamic tools)
        notification   -> has `method`, no `id`          (item/* and turn/* events)

    Responses resolve the matching outbound-request Future. Server requests and
    notifications are dispatched to per-thread queues by `threadId`.
    """

    def __init__(
        self,
        codex_bin: str = "codex",
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._bin = codex_bin
        self._extra_args = extra_args or []
        self._env = {**os.environ, **(env or {})}
        self._proc: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._next_id = 0
        self._pending: dict[int, _Pending] = {}
        self._write_lock = asyncio.Lock()
        # Per-thread inbound dispatch. Each session installs its own queue.
        self._thread_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        # Messages that arrive before any thread queue exists (e.g. the very
        # first notifications) land here so nothing is dropped.
        self._orphan_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    # ---- lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        if shutil.which(self._bin) is None:
            raise FileNotFoundError(
                f"`{self._bin}` not found on PATH. Install Codex "
                "(npm i -g @openai/codex) and authenticate with `codex login`."
            )
        self._proc = await asyncio.create_subprocess_exec(
            self._bin, "app-server", *self._extra_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,  # surfaced via _drain_stderr
            env=self._env,
        )
        self._reader_task = asyncio.create_task(self._read_loop())
        asyncio.create_task(self._drain_stderr())
        log.info("codex app-server started (pid=%s)", self._proc.pid)

    async def close(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except TimeoutError:  # pragma: no cover
                self._proc.kill()
        # Fail any in-flight requests so awaiters don't hang.
        for pend in self._pending.values():
            if not pend.future.done():
                pend.future.set_exception(ConnectionError("app-server closed"))
        self._pending.clear()

    # ---- thread queue registration ----------------------------------------

    def register_thread(self, thread_id: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._thread_queues[thread_id] = q
        return q

    def unregister_thread(self, thread_id: str) -> None:
        self._thread_queues.pop(thread_id, None)

    # ---- outbound ----------------------------------------------------------

    async def _write(self, message: dict[str, Any]) -> None:
        assert self._proc and self._proc.stdin
        line = json.dumps(message, separators=(",", ":")) + "\n"
        async with self._write_lock:
            self._proc.stdin.write(line.encode("utf-8"))
            await self._proc.stdin.drain()

    async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._next_id += 1
        req_id = self._next_id
        fut: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
        self._pending[req_id] = _Pending(fut)
        await self._write({"method": method, "id": req_id, "params": params})
        result = await fut
        return result

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        await self._write({"method": method, "params": params})

    async def respond(self, req_id: int, result: dict[str, Any]) -> None:
        """Answer a *server-initiated* request (approval / dynamic tool call)."""
        await self._write({"id": req_id, "result": result})

    async def respond_error(self, req_id: int, code: int, message: str) -> None:
        await self._write({"id": req_id, "error": {"code": code, "message": message}})

    # ---- inbound -----------------------------------------------------------

    async def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        try:
            while True:
                raw = await self._proc.stdout.readline()
                if not raw:
                    break  # EOF: server exited
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:  # pragma: no cover
                    log.warning("non-JSON line from app-server: %s", line[:200])
                    continue
                self._dispatch(msg)
        except asyncio.CancelledError:  # pragma: no cover
            pass
        except Exception as exc:  # pragma: no cover
            log.exception("app-server read loop crashed: %s", exc)

    def _dispatch(self, msg: dict[str, Any]) -> None:
        has_id = "id" in msg
        has_method = "method" in msg

        if has_id and not has_method:
            # Response to one of our outbound requests.
            pend = self._pending.pop(msg["id"], None)
            if pend and not pend.future.done():
                if "error" in msg:
                    pend.future.set_exception(
                        RuntimeError(f"app-server error: {msg['error']}")
                    )
                else:
                    pend.future.set_result(msg.get("result", {}))
            return

        # Notifications and server requests both carry `method`. Route by thread.
        params = msg.get("params") or {}
        thread_id = (
            params.get("threadId")
            or (params.get("thread") or {}).get("id")
            or (params.get("item") or {}).get("threadId")
        )
        q = self._thread_queues.get(thread_id) if thread_id else None
        (q or self._orphan_queue).put_nowait(msg)


# ============================================================================
# Section 4 — Per-session state
# ============================================================================

@dataclass
class _SessionState:
    thread_id: str
    turn_id: str | None = None
    inbound: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    # Maps a tool_use_id we minted -> the app-server server-request id we must
    # answer when the orchestrator asend()s the ToolResult.
    pending_approvals: dict[str, int] = field(default_factory=dict)


# ============================================================================
# Section 5 — CodexAdapter
# ============================================================================

class CodexAdapter(IKernelAdapter):
    """Codex kernel adapter — drives `codex app-server` over stdio JSON-RPC.

    Threading: one app-server process hosts many threads. Each `spawn_agent()`
    call starts its own thread + turn and consumes that thread's event queue.
    Do not share a single in-flight spawn_agent generator across asyncio tasks.
    """

    def __init__(
        self,
        codex_bin: str = "codex",
        *,
        execution_boundary: str = "kernel",     # "kernel" | "forge"
        approval_policy: str = "unlessTrusted",  # asks before non-trusted actions
        default_model: str = "gpt-5.4",
        cwd: str | None = None,
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
        client_name: str = "forge_os",
        client_version: str = "0.1.0",
    ) -> None:
        if execution_boundary not in ("kernel", "forge"):
            raise ValueError("execution_boundary must be 'kernel' or 'forge'")
        self._client = _AppServerClient(codex_bin, extra_args, env)
        self._execution_boundary = execution_boundary
        self._approval_policy = approval_policy
        self._default_model = default_model
        self._cwd = cwd or os.getcwd()
        self._client_name = client_name
        self._client_version = client_version
        self._initialized = False
        self._init_lock = asyncio.Lock()

    # ---- context-manager sugar --------------------------------------------

    async def __aenter__(self) -> CodexAdapter:
        await self._ensure_initialized()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._client.close()

    async def _ensure_initialized(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return
            await self._client.start()
            await self._client.request(
                "initialize",
                {
                    "clientInfo": {
                        "name": self._client_name,
                        "title": "Forge OS",
                        "version": self._client_version,
                    },
                    # Stay on the stable surface; flip to True only if you wire
                    # the experimental dynamicTools path in Section 7.
                    "capabilities": {"experimentalApi": False},
                },
            )
            await self._client.notify("initialized", {})
            self._initialized = True
            log.info("codex app-server initialized (boundary=%s)",
                     self._execution_boundary)

    # ---- FR-KA-001: capabilities ------------------------------------------

    def get_capabilities(self) -> KernelCapabilities:
        return KernelCapabilities(
            kernel_id=adapter_id,
            streaming=True,
            deterministic_output=False,
            extended_thinking=True,
            prompt_caching=False,
            vision=False,
            batch_api=False,
            hooks_native=False,
            subagents_native=False,
            mcp_remote=True,
            mcp_local_stdio=True,
            client_tools=["Read", "Write", "Edit", "Bash"],
            server_tools=["web_search"],
            max_context_tokens=128_000,
            notes={
                "native_approval_boundary": (
                    "Codex emits approval requests before each side-effecting "
                    "action. Forge's Validator intercepts these natively — no MCP "
                    "proxy shim required (unlike Claude SDK and OpenCode adapters)."
                ),
                "execution_boundary": (
                    "'kernel': Forge vets, Codex executes. "
                    "'forge': sandbox=readOnly + Forge MCP proxy executes."
                ),
            },
        )

    # ---- FR-KA-004: spawn_agent (the Proposal-boundary generator) ----------

    async def spawn_agent(  # type: ignore[override]
        self,
        persona: AgentPersona,
        context: str,
        tools: list[str],
        aggregate_id: str,
        *,
        mcp_servers: list[dict[str, Any]] | None = None,
        timeout_s: float = 600.0,
    ) -> AsyncIterator[NormalizedEvent]:
        """Run one agent turn against Codex, yielding normalized events.

        Yields ToolUseProposal for every side-effecting action Codex wants to
        take, then pauses. The caller runs it through Forge's Validator +
        Executor and resumes via `agen.asend(ToolResult(...))`.
        """
        await self._ensure_initialized()
        aggregate_id = aggregate_id or f"codex-{uuid.uuid4().hex[:8]}"  # keep for safety
        model = persona.preferred_model or self._default_model

        sandbox = (
            {"type": "readOnly", "access": {"type": "fullAccess"}}
            if self._execution_boundary == "forge"
            else {
                "type": "workspaceWrite",
                "writableRoots": [self._cwd],
                "networkAccess": True,
            }
        )

        # 1) Start a thread for this agent.
        start_params: dict[str, Any] = {
            "model": model,
            "cwd": self._cwd,
            "approvalPolicy": self._approval_policy,
            "sandbox": sandbox,
            "serviceName": self._client_name,
        }
        result = await self._client.request("thread/start", start_params)
        thread_id = result["thread"]["id"]
        q = self._client.register_thread(thread_id)
        sess = _SessionState(thread_id=thread_id, inbound=q)

        # 2) Apply the persona. Codex has no single "system prompt" knob on the
        #    stable API, so we (a) set the goal and (b) prepend a persona
        #    preamble to the first turn input. (If you opt into experimental
        #    collaborationMode, you can pass settings.developer_instructions
        #    instead — see module docstring.)
        try:
            await self._client.request(
                "thread/goal/set",
                {
                    "threadId": thread_id,
                    "objective": persona.goal[:4000] or persona.role[:4000],
                    "status": "active",
                    **({"tokenBudget": persona.thinking_budget_tokens}
                       if persona.thinking_budget_tokens else {}),
                },
            )
        except Exception as exc:  # goal is best-effort; don't fail the agent
            log.debug("thread/goal/set skipped: %s", exc)

        preamble = self._build_persona_preamble(persona, tools)

        try:
            # 3) Begin the turn.
            turn = await self._client.request(
                "turn/start",
                {
                    "threadId": thread_id,
                    "input": [{"type": "text", "text": f"{preamble}\n\n{context}"}],
                },
            )
            sess.turn_id = turn.get("turn", {}).get("id")

            yield NormalizedEvent(
                kind=EventKind.SESSION_STARTED,
                aggregate_id=aggregate_id,
                payload={"thread_id": thread_id, "turn_id": sess.turn_id,
                         "kernel": adapter_id, "model": model},
            )

            # 4) Consume the event stream, translating to normalized events and
            #    honoring the asend() Proposal-boundary handshake.
            async for normalized, server_req_id in self._translate_stream(sess, aggregate_id):
                if isinstance(normalized, ToolUseProposal):
                    # Hand the proposal out; wait for the orchestrator's verdict.
                    tool_result: ToolResult | None = (yield normalized)
                    if tool_result is None:
                        # Caller iterated without deciding — treat as a decline
                        # so Codex doesn't block forever.
                        tool_result = ToolResult(
                            tool_use_id=normalized.tool_use_id,
                            content="no decision supplied", is_error=True,
                        )
                    await self._answer_proposal(sess, normalized, tool_result, server_req_id)
                else:
                    yield normalized
                    if normalized.kind in (EventKind.AGENT_COMPLETED,
                                           EventKind.AGENT_FAILED):
                        return
        finally:
            self._client.unregister_thread(thread_id)

    # ---- event translation (FR-KA-005) ------------------------------------

    async def _translate_stream(
        self, sess: _SessionState, aggregate_id: str,
    ) -> AsyncIterator[tuple[NormalizedEvent, int | None]]:
        """Pull app-server messages for this thread and emit (event, req_id).

        req_id is non-None only for proposals that correspond to a pending
        server request the adapter must answer.
        """
        while True:
            msg = await sess.inbound.get()
            method = msg.get("method", "")
            params = msg.get("params") or {}
            server_req_id = msg.get("id")  # present for server-initiated requests

            # --- Approval requests => proposals (the Proposal boundary) ------
            if method in (
                "item/commandExecution/requestApproval",
                "item/fileChange/requestApproval",
            ):
                abstract = _abstract_tool_for_approval(method, params)
                tool_use_id = f"appr-{uuid.uuid4().hex[:8]}"
                if isinstance(server_req_id, int):
                    sess.pending_approvals[tool_use_id] = server_req_id
                inputs = self._approval_inputs(method, params)
                yield (
                    ToolUseProposal(
                        kind=EventKind.TOOL_USE_PROPOSED,
                        aggregate_id=aggregate_id,
                        payload={"item_id": params.get("itemId"),
                                 "reason": params.get("reason")},
                        tool_use_id=tool_use_id,
                        tool_name=("apply_patch"
                                   if method.startswith("item/fileChange") else "shell"),
                        abstract_tool=abstract,
                        inputs=inputs,
                    ),
                    server_req_id,
                )
                continue

            # --- Text + reasoning streaming ----------------------------------
            if method == "item/agentMessage/delta":
                yield (NormalizedEvent(EventKind.TEXT_DELTA, aggregate_id,
                                       {"text": params.get("delta", "")}), None)
                continue
            if method in ("item/reasoning/summaryTextDelta",
                          "item/reasoning/textDelta"):
                yield (NormalizedEvent(EventKind.THINKING_DELTA, aggregate_id,
                                       {"text": params.get("delta", "")}), None)
                continue

            # --- Plan / diff progress ---------------------------------------
            if method == "turn/plan/updated":
                yield (NormalizedEvent(EventKind.PLAN_UPDATED, aggregate_id,
                                       {"plan": params.get("plan", []),
                                        "explanation": params.get("explanation")}), None)
                continue
            if method == "turn/diff/updated":
                yield (NormalizedEvent(EventKind.DIFF_UPDATED, aggregate_id,
                                       {"diff": params.get("diff", "")}), None)
                continue

            # --- Kernel-executed tools (audit-tagged, not Forge-executed) ----
            if method == "item/completed":
                item = params.get("item") or {}
                itype = item.get("type")
                if itype == "webSearch":
                    yield (NormalizedEvent(EventKind.SERVER_TOOL_EXECUTED, aggregate_id,
                                           {"tool": "web_search",
                                            "query": item.get("query"),
                                            "execution": "kernel_executed"}), None)
                    continue
                if itype in ("commandExecution", "fileChange") and \
                        self._execution_boundary == "kernel":
                    # Accepted built-in action that Codex ran in its sandbox.
                    yield (NormalizedEvent(EventKind.SERVER_TOOL_EXECUTED, aggregate_id,
                                           {"tool": itype, "status": item.get("status"),
                                            "execution": "kernel_executed",
                                            "item": item}), None)
                    continue
                if itype == "mcpToolCall":
                    # forge-mode: a Forge MCP tool ran. In a fully wired forge
                    # boundary this is observed AFTER the back-channel executed
                    # it (Section 7); here we surface it for the audit ledger.
                    yield (NormalizedEvent(EventKind.SERVER_TOOL_EXECUTED, aggregate_id,
                                           {"tool": item.get("tool"),
                                            "server": item.get("server"),
                                            "status": item.get("status"),
                                            "item": item}), None)
                    continue
                # Other completed items (userMessage, agentMessage, reasoning):
                # already covered by deltas; ignore the duplicate completion.
                continue

            # --- Turn lifecycle ---------------------------------------------
            if method == "turn/completed":
                status = (params.get("turn") or {}).get("status")
                if status == "failed":
                    err_payload = {
                        "status": status,
                        "error": (params.get("turn") or {}).get("error"),
                    }
                    yield (NormalizedEvent(EventKind.AGENT_FAILED, aggregate_id, err_payload), None)
                else:
                    yield (NormalizedEvent(EventKind.AGENT_COMPLETED, aggregate_id,
                                           {"status": status}), None)
                return
            if method == "error":
                yield (NormalizedEvent(EventKind.AGENT_FAILED, aggregate_id,
                                       {"error": params.get("error")}), None)
                return

            # Everything else (item/started, thread/status/changed,
            # tokenUsage, serverRequest/resolved, ...) is non-essential for the
            # normalized stream. Log at debug for observability.
            log.debug("codex passthrough: %s", method)

    @staticmethod
    def _approval_inputs(method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method.startswith("item/fileChange"):
            return {"changes": params.get("changes", []),
                    "grant_root": params.get("grantRoot")}
        if params.get("networkApprovalContext"):
            ctx = params["networkApprovalContext"]
            return {"host": ctx.get("host"), "protocol": ctx.get("protocol")}
        return {"command": params.get("command"), "cwd": params.get("cwd"),
                "command_actions": params.get("commandActions")}

    # ---- answering the orchestrator's verdict ------------------------------

    async def _answer_proposal(
        self,
        sess: _SessionState,
        proposal: ToolUseProposal,
        tool_result: ToolResult,
        server_req_id: int | None,
    ) -> None:
        """Translate Forge's ToolResult back into a Codex decision."""
        req_id = sess.pending_approvals.pop(proposal.tool_use_id, server_req_id)
        if not isinstance(req_id, int):
            log.warning("no app-server request id for %s; cannot answer",
                        proposal.tool_use_id)
            return
        await self._client.respond(req_id, self._approval_response(tool_result))

    @staticmethod
    def _approval_response(tool_result: ToolResult) -> dict[str, Any]:
        """Build the decision payload for an approval server request.

        VERIFY against `codex app-server generate-json-schema`: the decision is
        carried under a `decision` field with one of accept | acceptForSession
        | decline | cancel. This single function is the only place to fix if the
        installed schema uses a different shape.
        """
        if tool_result.is_error:
            return {"decision": "decline"}
        # The Validator/Executor approved. A content hint of "session" lets a
        # caller opt into acceptForSession to suppress repeat prompts.
        if isinstance(tool_result.content, str) and "session" in tool_result.content.lower():
            return {"decision": "acceptForSession"}
        return {"decision": "accept"}

    # ---- persona -> Codex --------------------------------------------------

    def _build_persona_preamble(
        self, persona: AgentPersona, tools: list[str] | None,
    ) -> str:
        lines = [
            "You are operating as a Forge OS stage agent. Follow these "
            "instructions exactly.",
            f"# Role\n{persona.role}",
            f"# Goal\n{persona.goal}",
        ]
        if persona.constraints:
            lines.append("# Constraints\n" + "\n".join(f"- {c}" for c in persona.constraints))
        allowed = tools or persona.allowed_tools
        if allowed:
            lines.append("# Allowed tools\n" + ", ".join(allowed))
        if self._execution_boundary == "forge":
            lines.append(
                "# Execution policy\nThe workspace is READ-ONLY to you. You may "
                "inspect files, but every file change or shell command MUST be "
                "performed by calling the Forge tools provided over MCP. Do not "
                "attempt to write files or run shell commands directly."
            )
        else:
            lines.append(
                "# Execution policy\nEach command or file change you propose "
                "will be reviewed before it runs. Make one well-justified "
                "proposal at a time."
            )
        if persona.output_contract:
            lines.append("# Output contract\n" + json.dumps(persona.output_contract))
        return "\n\n".join(lines)

    # ---- FR-KA-005: lifecycle hook injection -------------------------------

    async def on_event(self, event: NormalizedEvent) -> None:  # type: ignore[override]
        """Translate a Forge lifecycle event (Stop, PreToolUse, ...) into a
        context injection for the active thread.

        Codex supports appending to live history via `thread/inject_items` and
        steering an in-flight turn via `turn/steer`. We use inject for context
        the model should see on its next request without starting a user turn.
        """
        thread_id = event.get("thread_id")
        text = event.get("inject_text")
        if not thread_id or not text:
            return None
        try:
            await self._client.request(
                "thread/inject_items",
                {
                    "threadId": thread_id,
                    "items": [{
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": text}],
                    }],
                },
            )
            return text
        except Exception as exc:  # pragma: no cover
            log.debug("on_event inject skipped: %s", exc)
            return None

    # ---- FR-KA-003: memory -------------------------------------------------

    async def sync_memory(self, lkg_snapshot: dict[str, Any] | None = None) -> None:
        """No-op for MVP. Forge's LKG is authoritative; the kernel does not own
        memory. (Codex persists its own thread rollouts, but Forge ignores them.)
        """
        return None


# ============================================================================
# Section 7 — execution_boundary="forge": Forge-owned execution via MCP
# ============================================================================
# The "kernel" boundary above is fully wired and runs with nothing but the
# `codex` binary. The "forge" boundary makes Forge's Executor run every
# mutation, exactly like the OpenCode adapter, and reuses the SAME shared
# proxy + loopback back-channel.
#
# Process topology (identical to OpenCode's three-level chain):
#
#     Forge Python process
#        |  subprocess
#        v
#     codex app-server                     (Rust)
#        |  MCP stdio subprocess (per configured server)
#        v
#     forge_mcp_proxy.py                   (Python — grandchild of Forge)
#        |  HTTP loopback POST /propose
#        v
#     Forge back-channel handler -> Validator + Executor
#
# To enable it you need three things, none of which change the core loop above:
#
#   1. Tell Codex about the Forge MCP server. Codex reads MCP servers from
#      config.toml ([mcp_servers.<name>]) or via per-thread config writes
#      (config/value/write / config/batchWrite). Point it at forge_mcp_proxy.py
#      over stdio, passing FORGE_BACKCHANNEL_URL + FORGE_SESSION_ID in `env`,
#      e.g.:
#
#         [mcp_servers.forge]
#         command = "python"
#         args    = ["-m", "forge.kernel.forge_mcp_proxy"]
#         env     = { FORGE_BACKCHANNEL_URL = "http://127.0.0.1:<port>",
#                     FORGE_SESSION_ID = "<thread_id>" }
#
#      (Or call `config/mcpServer/reload` after writing it so loaded threads
#      pick it up.)
#
#   2. Stand up the loopback back-channel (POST /propose, GET /health) inside
#      the Forge process — the very same aiohttp server the OpenCode adapter
#      already bind()s. When the proxy POSTs a tool call, construct a
#      ToolUseProposal, push it onto the session queue, await a Future, and
#      return the ToolResult JSON in the HTTP response. This routes Forge's
#      *domain* tools (ProposeEvent, ReadLKG) and the Write/Edit/Bash proxies
#      through the identical asend() handshake used above.
#
#   3. Keep sandbox=readOnly (already set when execution_boundary="forge") so
#      Codex's built-in apply_patch/shell cannot mutate anything and the model
#      is steered to the Forge MCP tools by the persona preamble.
#
# The mcpToolCall items then arrive as `item/completed` with type mcpToolCall
# (surfaced above for the audit ledger). Because the proxy is a grandchild, it
# cannot share asyncio.Queue objects with this generator — hence the HTTP
# back-channel, exactly as documented for OpenCode. Wiring is intentionally
# left as the integration seam so the shared proxy stays the single source of
# truth across both kernels.


# ============================================================================
# Section 8 — Smoke test
# ============================================================================

async def _smoke_test() -> None:
    """Run with:  python codex_adapter.py --smoke

    Prerequisites:
      - `codex` on PATH (npm i -g @openai/codex)
      - Authenticated: `codex login`  OR  CODEX_API_KEY / OPENAI_API_KEY set
    """
    persona = AgentPersona(
        name="event-storming",
        role="You are an event storming facilitator for Forge OS.",
        goal="Propose exactly one domain event for a hello-world bounded context.",
        constraints=["Reply with one short paragraph.", "Do not edit any files."],
        allowed_tools=["ProposeEvent"],
        preferred_model=os.environ.get("CODEX_MODEL", "gpt-5.4"),
        thinking_budget_tokens=2048,
    )

    async with CodexAdapter(
        execution_boundary="kernel",
        default_model=persona.preferred_model,
    ) as adapter:
        caps = adapter.get_capabilities()
        print(f"[caps] kernel={caps.kernel_id} streaming={caps.streaming} "
              f"thinking={caps.extended_thinking} "
              f"native_approval={caps.native_approval_boundary}")
        print(f"[caps] client_tools={caps.client_tools} server_tools={caps.server_tools}")

        agen = adapter.spawn_agent(
            persona=persona,
            context="Sketch one domain event for a greeting service. "
                    "If you would run any command, propose it.",
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
                        content='{"validator": "stub", "ok": true}',
                        is_error=False,   # approve the proposed action
                    ))
                )
            except StopAsyncIteration:
                break

            pending = None
            if isinstance(event, ToolUseProposal):
                print(f"[proposal] {event.abstract_tool} ({event.tool_name}) "
                      f"inputs={event.inputs}")
                pending = event
            elif event.kind == EventKind.TEXT_DELTA:
                print(event.payload["text"], end="", flush=True)
            else:
                print(f"\n[event] {event.kind} {event.payload}")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    if "--smoke" in sys.argv:
        asyncio.run(_smoke_test())
    else:
        print(
            "Forge OS Codex kernel adapter.\n"
            "Run with --smoke to exercise it against a real `codex app-server`.\n"
            "Prerequisites:\n"
            "  - `codex` on PATH (npm i -g @openai/codex)\n"
            "  - `codex login`  OR  CODEX_API_KEY / OPENAI_API_KEY in the env\n"
        )