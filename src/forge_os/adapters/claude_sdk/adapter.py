"""ClaudeSDKAdapter — Claude Agent SDK kernel (FR-KA-001..005).

Twin of ClaudeRawAdapter. Identical normalized events, identical Proposal
boundary semantics. The difference: the agent loop is owned by the SDK
(wraps a bundled Claude Code CLI subprocess over JSON/stdio) instead of a
raw Messages API call.

How the Proposal boundary is preserved
---------------------------------------
The SDK ships with built-in tools (Read, Write, Edit, Bash, …). If Claude
calls those, the SDK executes them inside its own process — Forge's
Validator + Executor never see them, violating §2.7 Bounded Autonomy.

Prevention:
1. ``allowed_tools`` is set to ONLY the Forge proxy tools.
2. An in-process SDK MCP server (``forge-proxy``) is registered; each
   @tool is a thin shim that puts a ToolUseProposal on ``events_q``,
   blocks on the matching ToolResult from ``asend()``, and returns the
   content to the SDK. The shim never executes anything.
3. ``permission_mode="bypassPermissions"`` — SDK's permission layer is
   redundant once Forge owns every tool implementation.
4. ``setting_sources=[]`` so the agent does NOT pick up CLAUDE.md or
   filesystem hooks — Forge LKG is the authoritative context source.

Dependencies
------------
    pip install "claude-agent-sdk>=0.1.81"
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

try:
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        ClaudeSDKClient,
        create_sdk_mcp_server,
        tool,
    )
except ImportError as exc:
    raise ImportError(
        "ClaudeSDKAdapter requires 'claude-agent-sdk>=0.1.81'. "
        "Install it with: pip install 'claude-agent-sdk>=0.1.81'"
    ) from exc

from forge_os.kernel.types import (
    AgentPersona,
    EventKind,
    IKernelAdapter,
    KernelCapabilities,
    NormalizedEvent,
    ToolResult,
    ToolUseProposal,
)

log = logging.getLogger("forge.kernel.claude_sdk")

adapter_id = "claude_sdk"

# ---------------------------------------------------------------------------
# Forge abstract-tool schema registry (FR-KA-004)
# ---------------------------------------------------------------------------

FORGE_ABSTRACT_TOOLS: dict[str, dict[str, Any]] = {
    "Read": {
        "description": "Read the contents of a file from the workspace.",
        "input_schema": {"path": str},
    },
    "Write": {
        "description": "Write content to a file in the workspace (proposes a Write event).",
        "input_schema": {"path": str, "content": str},
    },
    "Edit": {
        "description": "Edit an existing file by find/replace (proposes an Edit event).",
        "input_schema": {"path": str, "old_str": str, "new_str": str},
    },
    "Bash": {
        "description": "Execute a shell command inside the Forge sandbox.",
        "input_schema": {"command": str, "timeout_s": int},
    },
    "Grep": {
        "description": "Search file contents using ripgrep.",
        "input_schema": {"pattern": str, "path": str},
    },
    "Glob": {
        "description": "Match files by pattern.",
        "input_schema": {"pattern": str, "path": str},
    },
    "WebFetch": {
        "description": "Fetch a URL through Forge's outbound proxy.",
        "input_schema": {"url": str, "prompt": str},
    },
    "ProposeEvent": {
        "description": (
            "Commit a domain event to the Forge event store. The "
            "Validator decides whether the event is accepted."
        ),
        "input_schema": {"event_type": str, "payload": dict},
    },
}


# ---------------------------------------------------------------------------
# Proxy-tool factory
# ---------------------------------------------------------------------------

def _build_forge_proxy_server(
    abstract_tools: list[str],
    events_q: asyncio.Queue,  # type: ignore[type-arg]
    results_q: asyncio.Queue,  # type: ignore[type-arg]
    aggregate_id: str,
    tool_timeout_s: float = 120.0,
) -> tuple[Any, list[str]]:
    """Build an in-process SDK MCP server whose tools proxy to Forge.

    Each proxy tool:
    1. Generates a tool_use_id and puts a ToolUseProposal on events_q.
    2. Awaits a matching ToolResult on results_q (with timeout).
    3. Returns the result content to the SDK.

    Returns (server, wire_allowed_tools).
    """

    def _make_proxy(abstract_name: str, spec: dict[str, Any]):
        wire_name = abstract_name.lower()
        description = spec["description"]
        input_schema = spec["input_schema"]

        @tool(wire_name, description, input_schema)
        async def proxy(args: dict[str, Any]) -> dict[str, Any]:
            tool_use_id = f"sdk-{uuid.uuid4().hex[:12]}"
            proposal = ToolUseProposal(
                kind=EventKind.TOOL_USE_PROPOSED,
                aggregate_id=aggregate_id,
                tool_use_id=tool_use_id,
                tool_name=f"mcp__forge__{wire_name}",
                abstract_tool=abstract_name,
                inputs=args,
                payload={"abstract_tool": abstract_name, "inputs": args},
            )
            await events_q.put(proposal)

            try:
                while True:
                    result: ToolResult = await asyncio.wait_for(
                        results_q.get(), timeout=tool_timeout_s
                    )
                    if result.tool_use_id == tool_use_id:
                        content = result.content
                        blocks = (
                            [{"type": "text", "text": content}]
                            if isinstance(content, str)
                            else content
                        )
                        return {"content": blocks, "is_error": result.is_error}
                    await results_q.put(result)
                    await asyncio.sleep(0)
            except TimeoutError:
                msg = (
                    f"[forge] Tool {abstract_name!r} timed out after "
                    f"{tool_timeout_s}s waiting for Validator/Executor."
                )
                return {"content": [{"type": "text", "text": msg}], "is_error": True}

        return proxy

    proxies = [
        _make_proxy(name, FORGE_ABSTRACT_TOOLS[name])
        for name in abstract_tools
        if name in FORGE_ABSTRACT_TOOLS
    ]
    for unknown in [n for n in abstract_tools if n not in FORGE_ABSTRACT_TOOLS]:
        log.warning("Unknown abstract tool %r — skipped", unknown)

    server = create_sdk_mcp_server(
        name="forge-proxy",
        version="1.0.0",
        tools=proxies,
    )
    wire_names = [
        f"mcp__forge-proxy__{name.lower()}"
        for name in abstract_tools
        if name in FORGE_ABSTRACT_TOOLS
    ]
    return server, wire_names


# ---------------------------------------------------------------------------
# ClaudeSDKAdapter
# ---------------------------------------------------------------------------

class ClaudeSDKAdapter(IKernelAdapter):
    """Forge kernel adapter backed by ``claude-agent-sdk``.

    One ``spawn_agent()`` per task. Internal queues are per-call, so
    multiple concurrent agents are fine — do not share an in-flight
    async generator across tasks.
    """

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "claude-opus-4-7",
        tool_timeout_s: float = 120.0,
    ) -> None:
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
        self._default_model = default_model
        self._tool_timeout_s = tool_timeout_s

    # -- FR-KA-002 ----------------------------------------------------------

    def get_capabilities(self) -> KernelCapabilities:
        return KernelCapabilities(
            kernel_id=adapter_id,
            streaming=True,
            deterministic_output=False,
            extended_thinking=True,
            prompt_caching=True,
            vision=True,
            batch_api=False,
            hooks_native=True,
            subagents_native=True,
            mcp_remote=True,
            mcp_local_stdio=True,
            client_tools=list(FORGE_ABSTRACT_TOOLS.keys()),
            server_tools=[],
            max_context_tokens=200_000,
            notes={
                "server_tools": (
                    "Anthropic server tools are NOT surfaced. The SDK calls them via "
                    "built-in tools, which are disabled to keep the Proposal boundary "
                    "intact. Route via Forge's Executor if needed."
                ),
                "batch_api": "Use the claude_raw kernel for Batch API workloads.",
                "hooks_native": (
                    "PreToolUse/PostToolUse/Stop hooks fire inside the SDK and are "
                    "routed to on_event(). Canonical Forge hooks still fire in the "
                    "orchestrator. Hook callbacks here are for diagnostics only."
                ),
                "agent_loop": (
                    "Unlike the raw adapter, the SDK owns the message loop. This is "
                    "the main performance variable to measure vs. claude_raw."
                ),
            },
        )

    # -- FR-KA-001 ----------------------------------------------------------

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
        """Run one agent turn cycle via the SDK and yield normalized events.

        Same contract as ClaudeRawAdapter.spawn_agent: caller MUST
        ``agen.asend(ToolResult)`` for every ToolUseProposal yielded, or
        the SDK side will time out after ``tool_timeout_s``.
        """
        allowed = set(tools)
        abstract_tools = [t for t in persona.allowed_tools if t in allowed]

        events_q: asyncio.Queue = asyncio.Queue()
        results_q: asyncio.Queue = asyncio.Queue()

        forge_server, wire_allowed = _build_forge_proxy_server(
            abstract_tools, events_q, results_q, aggregate_id,
            tool_timeout_s=self._tool_timeout_s,
        )
        options = self._build_options(persona, wire_allowed, forge_server)

        yield NormalizedEvent(
            kind=EventKind.SESSION_STARTED,
            aggregate_id=aggregate_id,
            payload={
                "persona": persona.name,
                "model": options.model,
                "kernel": adapter_id,
                "client_tools": abstract_tools,
                "setting_sources": persona.setting_sources,
            },
        )

        SENTINEL = object()

        async def _drive_sdk() -> None:
            try:
                async with ClaudeSDKClient(options=options) as client:
                    await client.query(context)
                    async for msg in client.receive_response():
                        cls = type(msg).__name__
                        if cls == "AssistantMessage":
                            for block in getattr(msg, "content", []) or []:
                                btype = (
                                    getattr(block, "type", None)
                                    or (block.get("type") if isinstance(block, dict) else None)
                                )
                                if btype == "text":
                                    text = (
                                        getattr(block, "text", None)
                                        or (
                                            block.get("text", "")
                                            if isinstance(block, dict) else ""
                                        )
                                    )
                                    await events_q.put(NormalizedEvent(
                                        kind=EventKind.TEXT_DELTA,
                                        aggregate_id=aggregate_id,
                                        payload={"text": text},
                                    ))
                                elif btype == "thinking":
                                    text = (
                                        getattr(block, "thinking", None)
                                        or (
                                            block.get("thinking", "")
                                            if isinstance(block, dict) else ""
                                        )
                                    )
                                    await events_q.put(NormalizedEvent(
                                        kind=EventKind.THINKING_DELTA,
                                        aggregate_id=aggregate_id,
                                        payload={"text": text},
                                    ))
                        elif cls == "ResultMessage":
                            subtype = getattr(msg, "subtype", "success")
                            kind = (
                                EventKind.AGENT_COMPLETED
                                if subtype == "success"
                                else EventKind.AGENT_FAILED
                            )
                            await events_q.put(NormalizedEvent(
                                kind=kind,
                                aggregate_id=aggregate_id,
                                payload={
                                    "result": getattr(msg, "result", None),
                                    "usage": getattr(msg, "usage", None),
                                    "total_cost_usd": getattr(msg, "total_cost_usd", None),
                                    "duration_ms": getattr(msg, "duration_ms", None),
                                    "session_id": getattr(msg, "session_id", None),
                                    "num_turns": getattr(msg, "num_turns", None),
                                },
                            ))
                            return
            except Exception as exc:
                log.exception("SDK driver failed")
                await events_q.put(NormalizedEvent(
                    kind=EventKind.AGENT_FAILED,
                    aggregate_id=aggregate_id,
                    payload={"error": repr(exc)},
                ))
            finally:
                await events_q.put(SENTINEL)

        driver_task = asyncio.create_task(_drive_sdk())

        try:
            async with asyncio.timeout(timeout_s):
                while True:
                    item = await events_q.get()
                    if item is SENTINEL:
                        return
                    sent = yield item
                    if isinstance(item, ToolUseProposal):
                        if not isinstance(sent, ToolResult):
                            raise RuntimeError(
                                "spawn_agent: caller must asend(ToolResult) after a "
                                f"ToolUseProposal, got {type(sent).__name__}"
                            )
                        await results_q.put(sent)
        finally:
            if not driver_task.done():
                driver_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await driver_task

    # -- FR-KA-005 ----------------------------------------------------------

    async def on_event(self, event: NormalizedEvent) -> None:
        log.debug("on_event kernel=%s kind=%s", adapter_id, event.kind)

    # -- FR-KA-001 ----------------------------------------------------------

    async def sync_memory(self, lkg_snapshot: dict[str, Any] | None = None) -> None:
        """No-op: LKG is authoritative. Lessons are injected via context."""

    # -----------------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------------

    def _build_system_prompt(self, persona: AgentPersona) -> str:
        constraints = "\n".join(f"- {c}" for c in persona.constraints) or "(none)"
        contract = persona.output_contract or {}
        return (
            f"# Role\n{persona.role}\n\n"
            f"# Goal\n{persona.goal}\n\n"
            f"# Constraints\n{constraints}\n\n"
            f"# Output contract\n{contract}\n\n"
            "# Operating principles\n"
            "- You are running inside Forge OS via the Claude Agent SDK. Your\n"
            "  outputs are PROPOSALS; the Validator may reject any of them.\n"
            "- Use the `mcp__forge-proxy__*` tools for ALL side effects. The\n"
            "  built-in Read/Write/Bash tools are intentionally disabled.\n"
            "- Use `propose_event` to commit any domain event.\n"
            "- Never assume a tool succeeded until you see its tool_result.\n"
            "- Do not invent file paths or APIs. Verify via `read` first.\n"
        )

    def _build_options(
        self,
        persona: AgentPersona,
        wire_allowed_tools: list[str],
        forge_server: Any,
    ) -> ClaudeAgentOptions:
        kwargs: dict[str, Any] = {
            "model": persona.preferred_model or self._default_model,
            "system_prompt": self._build_system_prompt(persona),
            "max_turns": 50,
            "permission_mode": "bypassPermissions",
            "allowed_tools": wire_allowed_tools,
            "mcp_servers": {"forge-proxy": forge_server},
            "setting_sources": persona.setting_sources,
        }
        if persona.enable_skills and persona.setting_sources:
            kwargs["skills"] = "all"
        if persona.thinking_budget_tokens:
            kwargs["extra_args"] = {
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": persona.thinking_budget_tokens,
                },
            }
        return ClaudeAgentOptions(**kwargs)


# ---------------------------------------------------------------------------
# Persona YAML loader
# ---------------------------------------------------------------------------

def load_persona_from_yaml(path: str) -> AgentPersona:
    import yaml  # lazy — only needed when loading persona files
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    overrides = raw.get("kernel_overrides", {})
    return AgentPersona(
        name=raw["name"],
        role=raw["role"],
        goal=raw["goal"],
        constraints=raw.get("constraints", []),
        allowed_tools=raw.get("allowed_tools", []),
        allowed_server_tools=raw.get("allowed_server_tools", []),
        output_contract=raw.get("output_contract", {}),
        preferred_model=overrides.get("preferred_model", "claude-opus-4-7"),
        max_tokens=overrides.get("max_tokens", 4096),
        temperature=overrides.get("temperature", 0.0),
        thinking_budget_tokens=overrides.get("thinking_budget_tokens"),
        setting_sources=overrides.get("setting_sources", []),
        enable_skills=overrides.get("enable_skills", False),
    )


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

async def _smoke_test() -> None:
    """Requires claude-agent-sdk installed and ``claude login`` done."""
    adapter = ClaudeSDKAdapter()
    caps = adapter.get_capabilities()
    print(f"[caps] kernel={caps.kernel_id} hooks_native={caps.hooks_native} "
          f"subagents={caps.subagents_native}")

    persona = AgentPersona(
        name="example-architect",
        role="Forge System Architect",
        goal="Sketch a minimal event-store schema for Forge OS as JSON.",
        constraints=["Output via the propose_event tool only.", "No prose."],
        allowed_tools=["Read", "ProposeEvent"],
        thinking_budget_tokens=2048,
    )

    agen = adapter.spawn_agent(
        persona=persona,
        context="Sketch the event store schema. Call read on 'specs/events.md', "
                "then propose_event.",
        tools=["Read", "ProposeEvent"],
        aggregate_id="smoke-001",
        timeout_s=120.0,
    )

    pending: ToolResult | None = None
    try:
        while True:
            ev = await (agen.asend(pending) if pending else agen.__anext__())
            pending = None
            if isinstance(ev, ToolUseProposal):
                print(f"[propose] {ev.abstract_tool} inputs={ev.inputs}")
                pending = ToolResult(tool_use_id=ev.tool_use_id, content="[stub ok]")
            elif ev.kind == EventKind.AGENT_COMPLETED:
                print(f"[done  ] {ev.payload}")
                break
            elif ev.kind == EventKind.AGENT_FAILED:
                print(f"[fail  ] {ev.payload}")
                break
            else:
                print(f"[event ] {ev.kind} {str(ev.payload)[:80]}")
    except StopAsyncIteration:
        pass


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if "--smoke" in sys.argv:
        asyncio.run(_smoke_test())
    else:
        print("Usage: python -m forge_os.adapters.claude_sdk.adapter --smoke")
        raise SystemExit(1)
