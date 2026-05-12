"""Phase 08.5 Async Kernel Adapter interface.

Defines the async KernelAdapter protocol alongside the existing sync version.
Both coexist to enable incremental migration.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from forge_os.agents.models import AgentDefinition, OutputArtifact
from forge_os.events.model import LifecycleEvent
from forge_os.schemas.state import PipelineState

ToolList = list[str]


class AsyncAgentHandle(BaseModel):
    """Provider-neutral handle returned by `AsyncKernelAdapter.spawn_agent`."""

    model_config = ConfigDict(extra="allow")

    handle_id: str = Field(default_factory=lambda: f"async-agent-{uuid4()}")
    provider: str
    persona_id: str
    stage_id: str | None = None
    status: str = "running"
    outputs: list[OutputArtifact] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AsyncEventResponse(BaseModel):
    """Normalized response from async adapter lifecycle event handling."""

    model_config = ConfigDict(extra="allow")

    handled: bool = True
    actions: list[str] = Field(default_factory=list)
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class AsyncKernelAdapter(Protocol):
    """Async version of the KernelAdapter protocol.

    Methods are async def. Use alongside the sync KernelAdapter protocol
    for incremental migration. Converters and adapters bridge the two.
    """

    adapter_id: str

    async def spawn_agent(
        self,
        persona: AgentDefinition,
        context: str,
        tools: ToolList,
    ) -> AsyncAgentHandle:
        """Start an agent asynchronously and return a normalized handle."""
        ...

    async def on_event(
        self,
        event: LifecycleEvent,
        session: PipelineState,
    ) -> AsyncEventResponse:
        """Translate or process a Forge lifecycle event asynchronously."""
        ...

    async def get_default_tools(self) -> ToolList:
        """Return default abstract tools supported by this adapter."""
        ...

    async def supports(self, capability: str) -> bool:
        """Return whether an optional runtime capability is available."""
        ...

    # ── ACP Integration (Phase 08, async variant) ──────────────────────────

    async def get_acp_registry_adapter(self) -> object:
        """Return the ACP Registry adapter for agent discovery and installation."""
        ...

    async def spawn_acp_agent(
        self,
        agent_id: str,
        session_id: str | None = None,
    ) -> object:
        """Spawn an ACP-compatible agent from the registry asynchronously."""
        ...

    async def list_acp_agents(self) -> list[dict[str, object]]:
        """List all ACP agents available in the registry."""
        ...

    async def is_acp_available(self) -> bool:
        """Check if ACP mode is available (registry accessible)."""
        ...


class AsyncBaseKernelAdapter:
    """Convenience async base class for adapters.

    Provides default implementations for optional methods.
    """

    adapter_id = "async-base"
    optional_capabilities: frozenset[str] = frozenset()

    async def supports(self, capability: str) -> bool:
        return capability in self.optional_capabilities

    async def _intersect_tools(self, requested: Iterable[str]) -> ToolList:
        defaults_set = await self.get_default_tools()
        return [tool for tool in requested if tool in set(defaults_set)]

    async def on_event(
        self,
        event: LifecycleEvent,
        session: PipelineState,
    ) -> AsyncEventResponse:
        return AsyncEventResponse(
            handled=True,
            actions=[],
            message=f"{self.adapter_id} observed {event.event_type}",
            metadata={"project_id": session.project_id},
        )

    async def get_default_tools(self) -> ToolList:
        return []

    # ── ACP Integration (Phase 08) ────────────────────────────────────────

    async def get_acp_registry_adapter(self) -> object:
        from forge_os.adapters.base import UnsupportedAdapterCapability

        raise UnsupportedAdapterCapability(
            f"Adapter {self.adapter_id} does not support ACP registry access"
        )

    async def spawn_acp_agent(
        self,
        agent_id: str,
        session_id: str | None = None,
    ) -> object:
        from forge_os.adapters.base import UnsupportedAdapterCapability

        raise UnsupportedAdapterCapability(
            f"Adapter {self.adapter_id} does not support ACP agent spawning"
        )

    async def list_acp_agents(self) -> list[dict[str, object]]:
        return []

    async def is_acp_available(self) -> bool:
        return False
