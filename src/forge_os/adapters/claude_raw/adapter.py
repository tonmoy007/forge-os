"""ClaudeRawAdapter — raw Anthropic Messages API kernel (FR-KA-001..005).

Forge OS's Validator/Executor pipeline IS the orchestration loop. The raw
Messages API is used deliberately — the Agent SDK would attempt to own that
responsibility, breaking the Proposal boundary (§2.7 Bounded Autonomy).

Design invariants
-----------------
1. Dumb adapter: never executes client tools. Yields ToolUseProposal and
   pauses; caller runs Validator + Executor and feeds ToolResult back via
   the async generator's ``asend()`` method.
2. No state mutation: all state changes go through the Proposal boundary.
3. No memory ownership: Forge's LKG is authoritative; ``sync_memory()`` is
   a no-op for MVP.
4. Server tools (web_search, code_execution, etc.) run on Anthropic
   infrastructure. They bypass the Forge Executor. The adapter emits
   SERVER_TOOL_EXECUTED events tagged ``kernel_executed`` (§3.34).

Dependencies
------------
    pip install "anthropic>=0.40"
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

try:
    import anthropic
except ImportError as exc:
    raise ImportError(
        "ClaudeRawAdapter requires 'anthropic>=0.40'. "
        "Install it with: pip install 'anthropic>=0.40'"
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

log = logging.getLogger("forge.kernel.claude_raw")

adapter_id = "claude_raw"

# ---------------------------------------------------------------------------
# Tool registry (FR-KA-004)
# ---------------------------------------------------------------------------
# Maps Forge abstract names → Anthropic tool schemas.
# Personas reference abstract names only — never wire names.

ANTHROPIC_CLIENT_TOOLS: dict[str, dict[str, Any]] = {
    "Bash":       {"type": "bash_20250124",        "name": "bash"},
    "TextEditor": {"type": "text_editor_20250429", "name": "str_replace_based_edit_tool"},
    "Computer":   {"type": "computer_20250124",    "name": "computer",
                   "display_width_px": 1024, "display_height_px": 768},
}

ANTHROPIC_SERVER_TOOLS: dict[str, dict[str, Any]] = {
    "WebSearch":     {"type": "web_search_20250305",     "name": "web_search"},
    "WebFetch":      {"type": "web_fetch_20250910",      "name": "web_fetch"},
    "CodeExecution": {"type": "code_execution_20250522", "name": "code_execution"},
    "ToolSearch":    {"type": "tool_search_20250910",    "name": "tool_search"},
}

FORGE_CUSTOM_TOOLS: dict[str, dict[str, Any]] = {
    "Read": {
        "name": "read_file",
        "description": "Read a file from the workspace (subject to persona path allowlist).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "view_range": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["path"],
        },
    },
    "Write": {
        "name": "write_file",
        "description": "Propose a write to a file. Validator decides if it commits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    "ProposeEvent": {
        "name": "propose_event",
        "description": (
            "Propose an event for the Forge event store. The Validator checks "
            "the proposal against gate policies before it is appended."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_type":   {"type": "string"},
                "aggregate_id": {"type": "string"},
                "data":         {"type": "object"},
            },
            "required": ["event_type", "aggregate_id", "data"],
        },
    },
}


def _build_wire_to_abstract() -> dict[str, str]:
    m: dict[str, str] = {}
    for abstract, spec in ANTHROPIC_CLIENT_TOOLS.items():
        m[spec["name"]] = abstract
    for abstract, spec in ANTHROPIC_SERVER_TOOLS.items():
        m[spec["name"]] = abstract
    for abstract, spec in FORGE_CUSTOM_TOOLS.items():
        m[spec["name"]] = abstract
    return m


_WIRE_TO_ABSTRACT: dict[str, str] = _build_wire_to_abstract()


def build_tool_payload(
    abstract_client_tools: list[str],
    abstract_server_tools: list[str],
) -> tuple[list[dict[str, Any]], set[str]]:
    """Build the Anthropic ``tools=[…]`` payload from abstract names.

    Returns ``(tools_payload, server_tool_wire_names)``. The second value
    lets the streaming dispatch quickly identify which tool_use blocks are
    server-side versus client-side.
    """
    tools: list[dict[str, Any]] = []
    server_wire_names: set[str] = set()

    for name in abstract_client_tools:
        if name in ANTHROPIC_CLIENT_TOOLS:
            tools.append(dict(ANTHROPIC_CLIENT_TOOLS[name]))
        elif name in FORGE_CUSTOM_TOOLS:
            spec = dict(FORGE_CUSTOM_TOOLS[name])
            spec["strict"] = True
            tools.append(spec)
        else:
            log.warning("Unknown abstract client tool %r — skipped", name)

    for name in abstract_server_tools:
        if name in ANTHROPIC_SERVER_TOOLS:
            spec = dict(ANTHROPIC_SERVER_TOOLS[name])
            tools.append(spec)
            server_wire_names.add(spec["name"])
        else:
            log.warning("Unknown abstract server tool %r — skipped", name)

    return tools, server_wire_names


# ---------------------------------------------------------------------------
# ClaudeRawAdapter
# ---------------------------------------------------------------------------

class ClaudeRawAdapter(IKernelAdapter):
    """Anthropic Claude kernel via raw Messages API.

    Each ``spawn_agent()`` call opens its own HTTP stream. Do not share an
    in-flight async generator across tasks.
    """

    MCP_BETA_HEADER = "mcp-client-2025-11-20"

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "claude-opus-4-7",
        max_retries: int = 3,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            max_retries=max_retries,
        )
        self._default_model = default_model

    # -- FR-KA-002 ----------------------------------------------------------

    def get_capabilities(self) -> KernelCapabilities:
        return KernelCapabilities(
            kernel_id=adapter_id,
            streaming=True,
            deterministic_output=False,
            extended_thinking=True,
            prompt_caching=True,
            vision=True,
            batch_api=True,
            hooks_native=False,
            subagents_native=False,
            mcp_remote=True,
            mcp_local_stdio=False,
            client_tools=list(ANTHROPIC_CLIENT_TOOLS) + list(FORGE_CUSTOM_TOOLS),
            server_tools=list(ANTHROPIC_SERVER_TOOLS),
            max_context_tokens=200_000,
            notes={
                "server_tools": (
                    "Server tools execute on Anthropic infrastructure and bypass "
                    "the Forge Executor. Audit Ledger MUST tag SERVER_TOOL_EXECUTED "
                    "events as kernel_executed (§3.34)."
                ),
                "determinism": (
                    "No LLM is byte-deterministic. The Proposal/Validator/Executor "
                    "boundary (§2.7) is mandatory for this kernel."
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
        """Stream a Claude agent session.

        Multi-turn loop semantics:
        1. Yields TEXT_DELTA / THINKING_DELTA as Claude generates.
        2. On a client tool_use: yields ToolUseProposal and PAUSES.
           Caller does: ``result = await agen.asend(ToolResult(…))``
        3. On a server_tool_use+result pair: yields SERVER_TOOL_EXECUTED.
           No ``asend()`` — already ran on kernel side.
        4. On stop_reason="end_turn": yields AGENT_COMPLETED and stops.
        5. On timeout/error: yields AGENT_FAILED.
        """
        allowed = set(tools)
        client_abstract = [t for t in persona.allowed_tools if t in allowed]
        server_abstract = [t for t in persona.allowed_server_tools if t in allowed]

        tools_payload, server_wire_names = build_tool_payload(
            client_abstract, server_abstract
        )
        system_blocks = self._build_system_prompt(persona)

        request_kwargs: dict[str, Any] = {
            "model": persona.preferred_model or self._default_model,
            "max_tokens": persona.max_tokens,
            "temperature": persona.temperature,
            "system": system_blocks,
        }
        if tools_payload:
            request_kwargs["tools"] = tools_payload

        if persona.thinking_budget_tokens:
            request_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": persona.thinking_budget_tokens,
            }
            request_kwargs["temperature"] = 1.0

        betas: list[str] = []
        if mcp_servers:
            request_kwargs["mcp_servers"] = mcp_servers
            betas.append(self.MCP_BETA_HEADER)
        if betas:
            request_kwargs["betas"] = betas

        messages: list[dict[str, Any]] = [{"role": "user", "content": context}]

        yield NormalizedEvent(
            kind=EventKind.SESSION_STARTED,
            aggregate_id=aggregate_id,
            payload={
                "persona": persona.name,
                "model": request_kwargs["model"],
                "client_tools": client_abstract,
                "server_tools": server_abstract,
                "mcp_servers": [s.get("name") for s in (mcp_servers or [])],
            },
        )

        try:
            async with asyncio.timeout(timeout_s):
                while True:
                    final_message, client_tool_uses, server_events = (
                        await self._run_one_turn(
                            {**request_kwargs, "messages": messages},
                            aggregate_id=aggregate_id,
                            server_wire_names=server_wire_names,
                        )
                    )

                    for ev in server_events:
                        yield ev

                    for delta_ev in final_message.__forge_deltas__:  # type: ignore[attr-defined]
                        yield delta_ev

                    stop = final_message.stop_reason
                    if stop != "tool_use":
                        yield NormalizedEvent(
                            kind=EventKind.AGENT_COMPLETED,
                            aggregate_id=aggregate_id,
                            payload={
                                "stop_reason": stop,
                                "usage": (
                                    final_message.usage.model_dump()
                                    if final_message.usage else {}
                                ),
                            },
                        )
                        return

                    messages.append({
                        "role": "assistant",
                        "content": [b.model_dump() for b in final_message.content],
                    })

                    tool_result_blocks: list[dict[str, Any]] = []
                    for tu in client_tool_uses:
                        abstract = _WIRE_TO_ABSTRACT.get(tu.name, tu.name)
                        proposal = ToolUseProposal(
                            kind=EventKind.TOOL_USE_PROPOSED,
                            aggregate_id=aggregate_id,
                            tool_use_id=tu.id,
                            tool_name=tu.name,
                            abstract_tool=abstract,
                            inputs=dict(tu.input) if tu.input else {},
                        )
                        result = yield proposal
                        if not isinstance(result, ToolResult):
                            raise RuntimeError(
                                f"ClaudeRawAdapter expected ToolResult via asend() "
                                f"after ToolUseProposal {tu.id!r}, "
                                f"got {type(result).__name__}"
                            )
                        tool_result_blocks.append({
                            "type": "tool_result",
                            "tool_use_id": result.tool_use_id,
                            "content": result.content,
                            "is_error": result.is_error,
                        })

                    messages.append({"role": "user", "content": tool_result_blocks})

        except TimeoutError:
            yield NormalizedEvent(
                kind=EventKind.AGENT_FAILED,
                aggregate_id=aggregate_id,
                payload={"reason": "timeout", "timeout_s": timeout_s},
            )
        except anthropic.APIError as exc:
            log.exception("Anthropic API error in spawn_agent")
            yield NormalizedEvent(
                kind=EventKind.AGENT_FAILED,
                aggregate_id=aggregate_id,
                payload={"reason": "api_error", "detail": str(exc)},
            )
        except Exception as exc:
            log.exception("Unexpected error in spawn_agent")
            yield NormalizedEvent(
                kind=EventKind.AGENT_FAILED,
                aggregate_id=aggregate_id,
                payload={"reason": "internal_error", "detail": repr(exc)},
            )

    # -- FR-KA-005 ----------------------------------------------------------

    async def on_event(self, event: NormalizedEvent) -> None:
        log.debug("on_event: %s aggregate=%s", event.kind, event.aggregate_id)

    # -- FR-KA-001 ----------------------------------------------------------

    async def sync_memory(self, lkg_snapshot: dict[str, Any] | None = None) -> None:
        """No-op. Forge LKG is authoritative; lessons are injected into the
        system prompt by the Context Pruner before each spawn_agent() call."""

    # -----------------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------------

    def _build_system_prompt(self, persona: AgentPersona) -> list[dict[str, Any]]:
        constraints = "\n".join(f"- {c}" for c in persona.constraints) or "(none)"
        contract = persona.output_contract or {}
        persona_text = (
            f"# Role\n{persona.role}\n\n"
            f"# Goal\n{persona.goal}\n\n"
            f"# Constraints\n{constraints}\n\n"
            f"# Output contract\n{contract}\n\n"
            "# Operating principles\n"
            "- You are running inside Forge OS. Your outputs are PROPOSALS;\n"
            "  the Validator may reject any of them before they commit.\n"
            "- Use the `propose_event` tool to commit any state change.\n"
            "- Never assume a tool succeeded until you see its tool_result.\n"
            "- Do not invent file paths, function names, or APIs. Verify via\n"
            "  Read or WebFetch first.\n"
        )
        return [
            {
                "type": "text",
                "text": persona_text,
                "cache_control": {"type": "ephemeral"},
            },
        ]

    async def _run_one_turn(
        self,
        request_kwargs: dict[str, Any],
        *,
        aggregate_id: str,
        server_wire_names: set[str],
    ) -> tuple[Any, list[Any], list[NormalizedEvent]]:
        """Stream one turn. Returns (final_message, client_tool_uses, server_events).

        Streamed text/thinking deltas are accumulated and attached to the final
        message as ``__forge_deltas__``.
        """
        deltas: list[NormalizedEvent] = []

        async with self._client.messages.stream(**request_kwargs) as stream:
            async for ev in stream:
                etype = getattr(ev, "type", None)
                if etype != "content_block_delta":
                    continue
                delta = getattr(ev, "delta", None)
                dtype = getattr(delta, "type", None)
                if dtype == "text_delta":
                    deltas.append(NormalizedEvent(
                        kind=EventKind.TEXT_DELTA,
                        aggregate_id=aggregate_id,
                        payload={"text": delta.text},
                    ))
                elif dtype == "thinking_delta":
                    deltas.append(NormalizedEvent(
                        kind=EventKind.THINKING_DELTA,
                        aggregate_id=aggregate_id,
                        payload={"thinking": delta.thinking},
                    ))

            final = await stream.get_final_message()

        final.__forge_deltas__ = deltas  # type: ignore[attr-defined]

        client_tool_uses: list[Any] = []
        server_events: list[NormalizedEvent] = []
        pending_server: dict[str, dict[str, Any]] = {}

        for block in final.content:
            btype = getattr(block, "type", None)
            if btype == "tool_use":
                if block.name in server_wire_names:
                    pending_server[block.id] = {
                        "name": block.name,
                        "inputs": dict(block.input) if block.input else {},
                    }
                else:
                    client_tool_uses.append(block)
            elif btype == "server_tool_use":
                pending_server[block.id] = {
                    "name": block.name,
                    "inputs": dict(block.input) if block.input else {},
                }
            elif btype and btype.endswith("_tool_result"):
                tu_id = getattr(block, "tool_use_id", None)
                rec = pending_server.pop(tu_id, None)
                if rec is None:
                    log.warning("Server tool_result with no matching tool_use: %s", tu_id)
                    continue
                server_events.append(NormalizedEvent(
                    kind=EventKind.SERVER_TOOL_EXECUTED,
                    aggregate_id=aggregate_id,
                    payload={
                        "tool_name": rec["name"],
                        "tool_use_id": tu_id,
                        "inputs": rec["inputs"],
                        "result": getattr(block, "content", None),
                        "kernel_executed": True,
                    },
                ))

        for tu_id, rec in pending_server.items():
            server_events.append(NormalizedEvent(
                kind=EventKind.SERVER_TOOL_EXECUTED,
                aggregate_id=aggregate_id,
                payload={
                    "tool_name": rec["name"],
                    "tool_use_id": tu_id,
                    "inputs": rec["inputs"],
                    "result": None,
                    "kernel_executed": True,
                    "warning": "no paired result block",
                },
            ))

        return final, client_tool_uses, server_events


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
    )


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

async def _smoke_test() -> None:
    """Requires ANTHROPIC_API_KEY in environment."""
    adapter = ClaudeRawAdapter()
    caps = adapter.get_capabilities()
    print(f"[caps] kernel={caps.kernel_id} streaming={caps.streaming} "
          f"thinking={caps.extended_thinking} mcp_remote={caps.mcp_remote}")

    persona = AgentPersona(
        name="example-architect",
        role="Forge System Architect",
        goal="Sketch a minimal event-store schema for Forge OS as JSON.",
        constraints=["Output via the propose_event tool only.", "No prose."],
        allowed_tools=["ProposeEvent"],
        allowed_server_tools=[],
        thinking_budget_tokens=2048,
    )

    agen = adapter.spawn_agent(
        persona=persona,
        context="Sketch the event store schema. Use propose_event.",
        tools=persona.allowed_tools,
        aggregate_id="smoke-001",
    )

    pending: ToolUseProposal | None = None
    while True:
        try:
            ev = await (
                agen.asend(None) if pending is None
                else agen.asend(ToolResult(
                    tool_use_id=pending.tool_use_id,
                    content='{"ack": true, "validator": "stub"}',
                ))
            )
        except StopAsyncIteration:
            break
        pending = None
        if isinstance(ev, ToolUseProposal):
            print(f"[proposal] {ev.abstract_tool} inputs={ev.inputs}")
            pending = ev
        else:
            print(f"[event] {ev.kind} payload={ev.payload}")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if "--smoke" in sys.argv:
        asyncio.run(_smoke_test())
    else:
        print("Usage: python -m forge_os.adapters.claude_raw.adapter --smoke")
        raise SystemExit(1)
