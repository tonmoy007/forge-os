"""AsyncToSyncBridge — wraps IKernelAdapter (async generator) to satisfy
the sync KernelAdapter Protocol used by AdapterRegistry (FR-KA-001).

The bridge runs the async generator to completion in a private event loop
(``asyncio.run()``). It auto-declines any ToolUseProposal with an error
ToolResult so the generator always terminates — the Forge Validator/Executor
pipeline has not been wired through this bridge yet.

When the full pipeline is wired in Phase 11, replace ``_AUTO_DECLINE`` with
real Validator + Executor calls.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from forge_os.adapters.base import AgentHandle, BaseKernelAdapter, EventResponse, ToolList
from forge_os.agents.models import AgentDefinition, OutputArtifact
from forge_os.events.model import LifecycleEvent
from forge_os.kernel.types import (
    AgentPersona,
    EventKind,
    IKernelAdapter,
    ToolResult,
    ToolUseProposal,
)
from forge_os.schemas.state import PipelineState

log = logging.getLogger("forge.adapters.bridge")


def _agent_def_to_persona(agent: AgentDefinition) -> AgentPersona:
    """Map Phase-05 AgentDefinition → kernel-layer AgentPersona."""
    return AgentPersona(
        name=agent.name,
        role=agent.role,
        goal=agent.prompt,
        allowed_tools=list(agent.default_tools),
    )


class AsyncToSyncBridge(BaseKernelAdapter):
    """Adapts an ``IKernelAdapter`` (async generator) to the sync
    ``KernelAdapter`` Protocol expected by ``AdapterRegistry``.

    Parameters
    ----------
    inner:
        Any IKernelAdapter implementation (HumanAdapter, ClaudeRawAdapter, …)
    auto_decline_proposals:
        When True (default), every ToolUseProposal is immediately declined with
        an error ToolResult so the generator terminates cleanly. Set to False
        only if you supply a custom ``proposal_handler``.
    proposal_handler:
        Optional async callable ``(ToolUseProposal) -> ToolResult``. When
        provided, each proposal is forwarded here instead of being auto-declined.
    """

    def __init__(
        self,
        inner: IKernelAdapter,
        *,
        auto_decline_proposals: bool = True,
        proposal_handler: Any = None,  # Callable[[ToolUseProposal], Awaitable[ToolResult]]
    ) -> None:
        self._inner = inner
        self._auto_decline = auto_decline_proposals
        self._proposal_handler = proposal_handler

        # Satisfy KernelAdapter.adapter_id requirement
        inner_id: str = getattr(inner, "adapter_id", type(inner).__name__.lower())
        self.adapter_id = f"bridge:{inner_id}"

    # ---- KernelAdapter.spawn_agent (sync) ------------------------------------

    def spawn_agent(
        self,
        persona: AgentDefinition,
        context: str,
        tools: ToolList,
    ) -> AgentHandle:
        """Run the inner async adapter to completion, return an AgentHandle.

        NOTE: must NOT be called from inside an already-running event loop
        (e.g. from within an asyncio task). For async callers, await
        ``spawn_agent_async()`` directly.
        """
        kernel_persona = _agent_def_to_persona(persona)
        try:
            result = asyncio.run(
                self._run_async(kernel_persona, context, tools, persona.id)
            )
        except Exception as exc:
            log.exception("AsyncToSyncBridge.spawn_agent failed")
            return AgentHandle(
                provider=self.adapter_id,
                persona_id=persona.id,
                status="failed",
                metadata={"error": repr(exc)},
            )
        return result

    async def spawn_agent_async(
        self,
        persona: AgentDefinition,
        context: str,
        tools: ToolList,
    ) -> AgentHandle:
        """Async version — use from inside an event loop."""
        kernel_persona = _agent_def_to_persona(persona)
        return await self._run_async(kernel_persona, context, tools, persona.id)

    async def _run_async(
        self,
        persona: AgentPersona,
        context: str,
        tools: ToolList,
        aggregate_id: str,
    ) -> AgentHandle:
        agen = self._inner.spawn_agent(
            persona=persona,
            context=context,
            tools=tools,
            aggregate_id=aggregate_id,
        )

        text_parts: list[str] = []
        status = "completed"
        fail_reason: str | None = None
        send_value: Any = None

        try:
            while True:
                try:
                    event = await agen.asend(send_value)
                except StopAsyncIteration:
                    break
                send_value = None

                if isinstance(event, ToolUseProposal):
                    result = await self._handle_proposal(event)
                    send_value = result

                elif event.kind == EventKind.TEXT_DELTA:
                    text_parts.append(event.payload.get("text", ""))

                elif event.kind == EventKind.AGENT_COMPLETED:
                    status = "completed"
                    break

                elif event.kind == EventKind.AGENT_FAILED:
                    status = "failed"
                    fail_reason = event.payload.get("reason") or str(event.payload)
                    break

        finally:
            try:
                await agen.aclose()
            except Exception:
                pass

        text = "".join(text_parts).strip()
        outputs: list[OutputArtifact] = []
        if text:
            outputs.append(OutputArtifact(path="(stream)", kind="text",
                                          description=text[:200]))

        return AgentHandle(
            provider=self.adapter_id,
            persona_id=persona.name,
            status=status,
            outputs=outputs,
            metadata={
                "fail_reason": fail_reason,
                "full_text": text,
            },
        )

    async def _handle_proposal(self, proposal: ToolUseProposal) -> ToolResult:
        if self._proposal_handler is not None:
            return await self._proposal_handler(proposal)
        if self._auto_decline:
            log.debug(
                "bridge: auto-declining ToolUseProposal %s (%s) — "
                "no Validator/Executor wired yet",
                proposal.tool_use_id, proposal.abstract_tool,
            )
            return ToolResult(
                tool_use_id=proposal.tool_use_id,
                content=(
                    f"[forge bridge] Tool execution not available yet "
                    f"(bridge auto-declined {proposal.abstract_tool!r}). "
                    "Wire a proposal_handler or use the full Forge pipeline."
                ),
                is_error=True,
            )
        raise RuntimeError(
            f"AsyncToSyncBridge: received ToolUseProposal {proposal.tool_use_id!r} "
            "but auto_decline_proposals=False and no proposal_handler was provided."
        )

    # ---- KernelAdapter stubs -------------------------------------------------

    def on_event(self, event: LifecycleEvent, session: PipelineState) -> EventResponse:
        return EventResponse(handled=True, message="bridge: no-op on_event")

    def get_default_tools(self) -> ToolList:
        caps = self._inner.get_capabilities()
        return list(caps.client_tools)

    def supports(self, capability: str) -> bool:
        caps = self._inner.get_capabilities()
        return capability in (caps.client_tools + caps.server_tools)
