"""Phase 05 Kernel Adapter interface."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from forge_os.agents.models import AgentDefinition, OutputArtifact
from forge_os.events.model import LifecycleEvent
from forge_os.schemas.state import PipelineState

if TYPE_CHECKING:
    from forge_os.events.store import EventStore

ToolList = list[str]


class AgentHandle(BaseModel):
    """Provider-neutral handle returned by `KernelAdapter.spawn_agent`."""

    model_config = ConfigDict(extra="allow")

    handle_id: str = Field(default_factory=lambda: f"agent-{uuid4()}")
    provider: str
    persona_id: str
    stage_id: str | None = None
    status: str = "running"
    outputs: list[OutputArtifact] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventResponse(BaseModel):
    """Normalized response from adapter lifecycle event handling."""

    model_config = ConfigDict(extra="allow")

    handled: bool = True
    actions: list[str] = Field(default_factory=list)
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class KernelAdapter(Protocol):
    """Minimal portable interface used by Forge OS Core."""

    adapter_id: str

    def spawn_agent(
        self,
        persona: AgentDefinition,
        context: str,
        tools: ToolList,
    ) -> AgentHandle:
        """Start an agent and return a normalized provider-neutral handle."""
        ...

    def on_event(self, event: LifecycleEvent, session: PipelineState) -> EventResponse:
        """Translate or process a Forge lifecycle event."""
        ...

    def get_default_tools(self) -> ToolList:
        """Return default abstract tools supported by this adapter."""
        ...

    def supports(self, capability: str) -> bool:
        """Return whether an optional runtime capability is available."""
        ...

    def bind_event_store(self, event_store: EventStore | None) -> None:
        """Attach an Event Store so spawns record lifecycle/cost events.

        No-op for adapters that do not record. Called on the production spawn
        path so a real `forge agent run` records to `.forge/events.db`.
        """
        ...

    # ── ACP Integration (Phase 08) ────────────────────────────────────────

    def get_acp_registry_adapter(self) -> object:  # ACPRegistryAdapter
        """Return the ACP Registry adapter for agent discovery and installation.

        Raises UnsupportedAdapterCapability if ACP is not available.
        """
        ...

    def spawn_acp_agent(self, agent_id: str, session_id: str | None = None) -> object:  # ACPClient
        """Spawn an ACP-compatible agent from the registry.

        Args:
            agent_id: Identifier from the ACP Registry.
            session_id: Optional existing session to resume.

        Returns an ACPClient ready for communication.
        """
        ...

    def list_acp_agents(self) -> list[dict[str, object]]:
        """List all ACP agents available in the registry."""
        ...

    def is_acp_available(self) -> bool:
        """Check if ACP mode is available (registry accessible)."""
        ...


class UnsupportedAdapterCapability(RuntimeError):
    """Raised when optional adapter control is requested but unsupported."""


class BaseKernelAdapter:
    """Convenience base class for adapters."""

    adapter_id = "base"
    optional_capabilities: frozenset[str] = frozenset()

    def supports(self, capability: str) -> bool:
        return capability in self.optional_capabilities

    def _intersect_tools(self, requested: Iterable[str]) -> ToolList:
        defaults = set(self.get_default_tools())
        return [tool for tool in requested if tool in defaults]

    def on_event(self, event: LifecycleEvent, session: PipelineState) -> EventResponse:
        return EventResponse(
            handled=True,
            actions=[],
            message=f"{self.adapter_id} observed {event.event_type}",
            metadata={"project_id": session.project_id},
        )

    def get_default_tools(self) -> ToolList:
        return []

    def bind_event_store(self, event_store: EventStore | None) -> None:
        """No-op by default; recording adapters override to capture the store."""
        return None

    # ── ACP Integration (Phase 08) ────────────────────────────────────────

    def get_acp_registry_adapter(self) -> object:
        raise UnsupportedAdapterCapability(
            f"Adapter {self.adapter_id} does not support ACP registry access"
        )

    def spawn_acp_agent(self, agent_id: str, session_id: str | None = None) -> object:
        raise UnsupportedAdapterCapability(
            f"Adapter {self.adapter_id} does not support ACP agent spawning"
        )

    def list_acp_agents(self) -> list[dict[str, object]]:
        return []

    def is_acp_available(self) -> bool:
        return False
