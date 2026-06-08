"""Canonical shared types for the Forge OS kernel adapter layer.

All kernel adapters (ClaudeRaw, ClaudeSDK, Codex, OpenCode, Human, …) import
from here. FR-KA-001..005.
"""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Event kinds
# ---------------------------------------------------------------------------

class EventKind(StrEnum):
    SESSION_STARTED      = "session_started"
    TEXT_DELTA           = "text_delta"
    THINKING_DELTA       = "thinking_delta"
    TOOL_USE_PROPOSED    = "tool_use_proposed"    # client tool → Proposal boundary
    SERVER_TOOL_EXECUTED = "server_tool_executed"  # ran on kernel side (audit-tagged)
    PLAN_UPDATED         = "plan_updated"          # Codex turn/plan/updated
    DIFF_UPDATED         = "diff_updated"          # Codex turn/diff/updated
    AGENT_COMPLETED      = "agent_completed"
    AGENT_FAILED         = "agent_failed"


# ---------------------------------------------------------------------------
# Event dataclasses
# ---------------------------------------------------------------------------

@dataclass
class NormalizedEvent:
    """A kernel-agnostic event yielded by spawn_agent()."""

    kind: EventKind
    aggregate_id: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolUseProposal(NormalizedEvent):
    """A client-tool proposal yielded at the Proposal boundary (§2.7).

    The caller MUST resume the async generator via ``agen.asend(ToolResult(…))``
    after receiving this event or the generator raises RuntimeError on next
    iteration.
    """

    tool_use_id: str = ""
    tool_name: str = ""      # wire name as the kernel reports it
    abstract_tool: str = ""  # Forge's abstract name (Read, Write, Bash, …)
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Returned to the adapter via asend() after Validator + Executor have run."""

    tool_use_id: str
    content: str | list[dict[str, Any]]
    is_error: bool = False


# ---------------------------------------------------------------------------
# Persona + capability dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AgentPersona:
    """Kernel-agnostic agent persona loaded from a Forge persona YAML (FR-AG-001).

    Kernel-specific overrides live under a ``kernel_overrides:`` block in the
    YAML and are surfaced here as typed fields. Adapters that need extra fields
    (e.g. OpenCode's ``primary_agent_template``) should define a subclass.
    """

    name: str
    role: str
    goal: str
    constraints: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)          # abstract names
    allowed_server_tools: list[str] = field(default_factory=list)   # abstract names
    output_contract: dict[str, Any] = field(default_factory=dict)

    # Kernel-specific overrides (FR-KA-003)
    preferred_model: str = "claude-opus-4-7"
    max_tokens: int = 4096
    temperature: float = 0.0
    thinking_budget_tokens: int | None = None   # None = thinking disabled

    # SDK-specific knobs (ignored by non-SDK adapters)
    setting_sources: list[str] = field(default_factory=list)  # [] | ["user","project","local"]
    enable_skills: bool = False                                # True → skills="all"


@dataclass
class KernelCapabilities:
    """Reported by IKernelAdapter.get_capabilities() (FR-KA-002).

    The Forge Capability Manager merges this with each stage's requirements
    and refuses to start a stage if a required capability is unavailable.
    """

    kernel_id: str
    streaming: bool
    deterministic_output: bool
    extended_thinking: bool
    prompt_caching: bool
    vision: bool
    batch_api: bool
    hooks_native: bool
    subagents_native: bool
    mcp_remote: bool
    mcp_local_stdio: bool
    client_tools: list[str]
    server_tools: list[str]
    max_context_tokens: int
    notes: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# IKernelAdapter ABC (FR-KA-001)
# ---------------------------------------------------------------------------

class IKernelAdapter(abc.ABC):
    """Language-agnostic kernel adapter contract.

    All kernel adapters implement this ABC. The protobuf mirror at
    ``forge/proto/kernel_adapter.proto`` is the canonical cross-language
    definition; this Python ABC stays in sync.
    """

    @abc.abstractmethod
    def get_capabilities(self) -> KernelCapabilities: ...

    @abc.abstractmethod
    def spawn_agent(
        self,
        persona: AgentPersona,
        context: str,
        tools: list[str],
        aggregate_id: str,
        *,
        mcp_servers: list[dict[str, Any]] | None = None,
        timeout_s: float = 600.0,
    ) -> AsyncIterator[NormalizedEvent]: ...

    @abc.abstractmethod
    async def on_event(self, event: NormalizedEvent) -> None: ...

    @abc.abstractmethod
    async def sync_memory(self, lkg_snapshot: dict[str, Any] | None = None) -> None: ...
