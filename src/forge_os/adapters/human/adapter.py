"""HumanAdapter — kernel whose 'model' is a person at a terminal (FR-KA-001..005).

This adapter lets a human operator drive the Forge pipeline through the same
IKernelAdapter interface as any LLM kernel. Every output and every tool proposal
still passes through the Proposal boundary (§2.7 Bounded Autonomy).

Usage:
    python -m forge_os.adapters.human.adapter --demo       # interactive
    python -m forge_os.adapters.human.adapter --caps       # print capabilities
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from collections.abc import AsyncIterator, Callable
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

log = logging.getLogger("forge.kernel.human")

adapter_id = "human"

# ---------------------------------------------------------------------------
# Proposable tool catalog (FR-KA-004)
# ---------------------------------------------------------------------------
# The operator may only propose tools from this set.  No server tools — a
# human has no server side.

FORGE_ABSTRACT_TOOLS: dict[str, dict[str, Any]] = {
    "Read":  {"desc": "Read a file (subject to the persona path allowlist).",
              "schema": {"path": "str", "view_range?": "[int, int]"}},
    "Write": {"desc": "Propose a write to a file. Validator decides if it commits.",
              "schema": {"path": "str", "content": "str"}},
    "Edit":  {"desc": "Propose an in-place edit (replace old text with new).",
              "schema": {"path": "str", "old": "str", "new": "str"}},
    "Bash":  {"desc": "Propose a shell command (runs in the sandbox, if allowed).",
              "schema": {"command": "str"}},
    "Grep":  {"desc": "Search file contents for a pattern.",
              "schema": {"pattern": "str", "path?": "str"}},
    "Glob":  {"desc": "List paths matching a glob pattern.",
              "schema": {"pattern": "str"}},
    "ProposeEvent": {"desc": "Append a domain event to the Event Store.",
                     "schema": {"type": "str", "payload": "object"}},
}


# ---------------------------------------------------------------------------
# HumanAdapter
# ---------------------------------------------------------------------------

class HumanAdapter(IKernelAdapter):
    """A kernel whose 'model' is a person at a terminal.

    Parameters
    ----------
    input_fn / print_fn:
        I/O injection points — testable without a real terminal.
    show_thinking:
        Whether to offer the [k] think action, which records THINKING_DELTA
        events useful for the Reflector / Lesson-Extractor.
    """

    adapter_id: str = "human"

    def __init__(
        self,
        input_fn: Callable[[str], str] = input,
        print_fn: Callable[[str], None] = print,
        show_thinking: bool = True,
    ) -> None:
        self._input_fn = input_fn
        self._print = print_fn
        self._show_thinking = show_thinking

    # -- FR-KA-002 ----------------------------------------------------------

    def get_capabilities(self) -> KernelCapabilities:
        return KernelCapabilities(
            kernel_id=adapter_id,
            streaming=False,
            deterministic_output=False,
            extended_thinking=False,
            prompt_caching=False,
            vision=True,
            batch_api=False,
            hooks_native=False,
            subagents_native=False,
            mcp_remote=False,
            mcp_local_stdio=False,
            client_tools=sorted(FORGE_ABSTRACT_TOOLS.keys()),
            server_tools=[],
            max_context_tokens=10 ** 9,
            notes={
                "purpose": "Test/reference kernel; a human plays the model role.",
                "cost": "Zero API spend — use to exercise the whole pipeline.",
                "determinism": "Never reproducible; do not use in deterministic gates.",
                "timeout": "timeout_s is advisory only; not enforced for a human.",
            },
        )

    # -- helpers ------------------------------------------------------------

    async def _ainput(self, prompt: str) -> str:
        return await asyncio.to_thread(self._input_fn, prompt)

    def _emit(self, line: str = "") -> None:
        self._print(line)

    def _briefing(self, persona: AgentPersona, context: str, tools: list[str]) -> str:
        allowed = [t for t in tools if t in FORGE_ABSTRACT_TOOLS] or tools
        tool_lines = "\n".join(
            f"    - {t}: {FORGE_ABSTRACT_TOOLS.get(t, {}).get('desc', '(custom)')}"
            for t in allowed
        )
        oc = persona.output_contract or {}
        oc_lines = (
            "\n".join(f"    - {k}: {v}" for k, v in oc.items())
            if oc else "    (none specified)"
        )
        constraints = (
            "\n".join(f"    - {c}" for c in persona.constraints)
            if persona.constraints else "    (none)"
        )
        return (
            "\n" + "=" * 72 + "\n"
            f"  FORGE HUMAN KERNEL — you are now acting as: {persona.name}\n"
            + "=" * 72 + "\n"
            f"\n  ROLE\n    {persona.role}\n"
            f"\n  GOAL\n    {persona.goal}\n"
            f"\n  CONSTRAINTS\n{constraints}\n"
            f"\n  OUTPUT CONTRACT\n{oc_lines}\n"
            f"\n  TOOLS YOU MAY PROPOSE\n{tool_lines}\n"
            f"\n  CONTEXT\n{_indent(context, '    ')}\n"
            + "-" * 72
        )

    def _menu(self) -> str:
        items = [
            "[s] say        add a line to your response",
            "[c] call tool  propose a tool call (-> Validator + Executor)",
            "[d] done       finish; emit AGENT_COMPLETED",
            "[x] abort      emit AGENT_FAILED and stop",
        ]
        if self._show_thinking:
            items.insert(1, "[k] think      record private reasoning (THINKING_DELTA)")
        return "\n".join(items)

    async def _read_choice(self) -> str:
        valid = {"s", "c", "d", "x"} | ({"k"} if self._show_thinking else set())
        while True:
            self._emit("\n" + self._menu())
            choice = (await self._ainput("> ")).strip().lower()[:1]
            if choice in valid:
                return choice
            self._emit(
                f"  ? unrecognized '{choice}'. Pick: {', '.join(sorted(valid))}"
            )

    async def _collect_proposal(
        self, allowed: list[str], aggregate_id: str
    ) -> ToolUseProposal:
        proposable = [t for t in allowed if t in FORGE_ABSTRACT_TOOLS] or allowed
        self._emit("  tools: " + ", ".join(proposable))
        while True:
            name = (await self._ainput("  tool name> ")).strip()
            if name in proposable:
                break
            self._emit(f"  ? '{name}' not in your set. Choose from: {', '.join(proposable)}")
        hint = FORGE_ABSTRACT_TOOLS.get(name, {}).get("schema")
        if hint:
            self._emit(f"  input schema: {json.dumps(hint)}")
        while True:
            raw = await self._ainput("  args (JSON)> ")
            try:
                inputs = json.loads(raw) if raw.strip() else {}
                if not isinstance(inputs, dict):
                    raise ValueError("top-level JSON must be an object")
                break
            except (json.JSONDecodeError, ValueError) as exc:
                self._emit(f"  ! invalid JSON ({exc}); e.g. {{\"path\": \"srs.md\"}}")
        return ToolUseProposal(
            kind=EventKind.TOOL_USE_PROPOSED,
            aggregate_id=aggregate_id,
            tool_use_id=f"human-{uuid.uuid4().hex[:12]}",
            tool_name=name,
            abstract_tool=name,
            inputs=inputs,
            payload={"tool": name, "inputs": inputs},
        )

    # -- FR-KA-001 / FR-KA-005 ---------------------------------------------

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
        """Run one human-driven agent turn, yielding normalized events.

        On ToolUseProposal the generator PAUSES; resume via
        ``agen.asend(ToolResult(…))``.
        """
        self._emit(self._briefing(persona, context, tools))
        yield NormalizedEvent(
            kind=EventKind.SESSION_STARTED,
            aggregate_id=aggregate_id,
            payload={"kernel": adapter_id, "persona": persona.name},
        )

        said: list[str] = []
        thought: list[str] = []

        try:
            while True:
                choice = await self._read_choice()

                if choice == "s":
                    line = await self._ainput("  say> ")
                    said.append(line)
                    yield NormalizedEvent(
                        kind=EventKind.TEXT_DELTA,
                        aggregate_id=aggregate_id,
                        payload={"text": line},
                    )

                elif choice == "k" and self._show_thinking:
                    line = await self._ainput("  think> ")
                    thought.append(line)
                    yield NormalizedEvent(
                        kind=EventKind.THINKING_DELTA,
                        aggregate_id=aggregate_id,
                        payload={"text": line},
                    )

                elif choice == "c":
                    proposal = await self._collect_proposal(tools, aggregate_id)
                    result = yield proposal
                    if not isinstance(result, ToolResult):
                        raise RuntimeError(
                            "HumanAdapter: ToolUseProposal must be resumed via "
                            f"asend(ToolResult(…)); got {type(result).__name__}."
                        )
                    flag = "ERROR" if result.is_error else "ok"
                    self._emit(
                        f"  <- tool result [{flag}] for {proposal.abstract_tool}:"
                    )
                    self._emit(_indent(_stringify(result.content), "     "))

                elif choice == "d":
                    yield NormalizedEvent(
                        kind=EventKind.AGENT_COMPLETED,
                        aggregate_id=aggregate_id,
                        payload={"text": "\n".join(said).strip(),
                                 "thinking": "\n".join(thought)},
                    )
                    return

                elif choice == "x":
                    reason = await self._ainput("  abort reason> ")
                    yield NormalizedEvent(
                        kind=EventKind.AGENT_FAILED,
                        aggregate_id=aggregate_id,
                        payload={"reason": reason or "operator aborted"},
                    )
                    return

        except (EOFError, KeyboardInterrupt):
            yield NormalizedEvent(
                kind=EventKind.AGENT_FAILED,
                aggregate_id=aggregate_id,
                payload={"reason": "operator interrupted (EOF/SIGINT)"},
            )

    # -- FR-KA-005 ----------------------------------------------------------

    async def on_event(self, event: NormalizedEvent) -> None:
        self._emit(
            f"  [forge:hook] {getattr(event.kind, 'value', event.kind)} "
            f"on {event.aggregate_id} {event.payload or ''}"
        )

    # -- FR-KA-001 ----------------------------------------------------------

    async def sync_memory(self, lkg_snapshot: dict[str, Any] | None = None) -> None:
        log.debug("HumanAdapter.sync_memory: no-op (LKG is authoritative)")


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _indent(text: str, pad: str) -> str:
    return "\n".join(pad + ln for ln in (text or "").splitlines()) or pad


def _stringify(content: Any) -> str:
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, indent=2)
    except (TypeError, ValueError):
        return str(content)


# ---------------------------------------------------------------------------
# Persona YAML loader
# ---------------------------------------------------------------------------

def load_persona_from_yaml(path: str) -> AgentPersona:
    import yaml  # lazy: only needed when loading persona files
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
# Interactive demo + capability printer
# ---------------------------------------------------------------------------

async def _demo() -> int:
    adapter = HumanAdapter()
    persona = AgentPersona(
        name="demo-architect",
        role="Forge System Architect (demo)",
        goal="Sketch a minimal event-store schema, then finish.",
        constraints=["Propose at least one tool call to feel the boundary."],
        allowed_tools=["Read", "Write", "ProposeEvent"],
        output_contract={"design.md": "markdown"},
    )
    agen = adapter.spawn_agent(
        persona=persona,
        context="This is a demo. Try [s], then [c], then [d].",
        tools=["Read", "Write", "ProposeEvent"],
        aggregate_id="agg-demo",
    )
    send: Any = None
    while True:
        try:
            ev = await (agen.asend(send) if send is not None else agen.__anext__())
        except StopAsyncIteration:
            break
        send = None
        if isinstance(ev, ToolUseProposal):
            print(f"\n  [orchestrator] would validate+execute "
                  f"{ev.abstract_tool}({json.dumps(ev.inputs)})")
            text = input("  type a fake tool result> ")
            send = ToolResult(tool_use_id=ev.tool_use_id, content=text or "(empty)")
        elif ev.kind == EventKind.AGENT_COMPLETED:
            print(f"\n  [done] {_indent(ev.payload.get('text', ''), '    ')}")
        elif ev.kind == EventKind.AGENT_FAILED:
            print(f"\n  [failed] {ev.payload.get('reason')}")
    print("\n  demo complete.")
    return 0


def _print_caps() -> int:
    caps = HumanAdapter().get_capabilities()
    for field_name, val in vars(caps).items():
        print(f"{field_name}: {val}")
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "--help"
    if arg == "--demo":
        raise SystemExit(asyncio.run(_demo()))
    elif arg == "--caps":
        raise SystemExit(_print_caps())
    else:
        print("Usage: python -m forge_os.adapters.human.adapter [--demo | --caps]")
        raise SystemExit(1)
