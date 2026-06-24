"""Phase 11 OpenClaw adapter schemas (additive — FR-OCA-001..006).

New schema file. Imports only stdlib + pydantic (schemas are pure data). No
existing schema/contract is modified — OpenClaw is an *optional* execution
surface and must never become a required dependency
(see ``plan/OPENCLAW_ADAPTER_ARCHITECTURE.md``).
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class OpenClawSessionConfig(BaseModel):
    """A Forge persona translated into an OpenClaw agent session config (FR-OCA-001).

    OpenClaw agents are configured by ``SOUL.md`` (identity/voice) and
    ``IDENTITY.md`` (role/goal) documents plus a system prompt. This is the
    kernel-agnostic persona projected onto those artifacts; the adapter sends it
    to the Gateway when starting a session.
    """

    agent_name: str
    soul_md: str
    identity_md: str
    system_prompt: str
    model: str = "claude-opus-4-7"
    allowed_tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)
    max_tokens: int = 4096
    temperature: float = 0.0


class OpenClawToolPolicy(BaseModel):
    """Result of mapping Forge tool categories to OpenClaw's allow/deny lists (FR-OCA-002).

    ``mismatches`` holds requested abstract tools with no OpenClaw wire mapping;
    they are logged and excluded (fail-closed) rather than silently passed.
    """

    allowlist: list[str] = Field(default_factory=list)
    denylist: list[str] = Field(default_factory=list)
    mismatches: list[str] = Field(default_factory=list)


class OpenClawWebhookKind(StrEnum):
    """Recognized OpenClaw webhook event kinds bridged to Forge events (FR-OCA-003)."""

    AGENT_MESSAGE = "agent.message"
    TOOL_PROPOSED = "tool.proposed"
    AGENT_STOPPED = "agent.stopped"
    AGENT_FAILED = "agent.failed"


class OpenClawWebhook(BaseModel):
    """An inbound OpenClaw Gateway webhook payload (FR-OCA-003).

    The adapter translates these into Forge lifecycle events; ``agent.stopped``
    drives the Forge ``Stop`` event that triggers reflection/gate/lesson work.
    """

    event: OpenClawWebhookKind
    session_id: str
    payload: dict = Field(default_factory=dict)
    timestamp: str | None = None
