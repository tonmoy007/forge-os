"""In-process lifecycle event bus."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from forge_os.events.log import append_event
from forge_os.events.model import EventType, LifecycleEvent, new_event
from forge_os.hooks.registry import HookRegistry, HookResult
from forge_os.schemas.state import PipelineState


class EventBus:
    """Append normalized events and dispatch in-process hooks."""

    def __init__(self, event_log_path: Path, hook_registry: HookRegistry | None = None) -> None:
        self.event_log_path: Path = event_log_path
        self.hook_registry: HookRegistry = hook_registry or HookRegistry()

    def emit(self, event: LifecycleEvent) -> list[HookResult]:
        """Append an event and dispatch hooks in deterministic order."""

        append_event(self.event_log_path, event)
        return self.hook_registry.run(event)

    def emit_transition(
        self,
        event_type: str,
        state: PipelineState,
        stage_id: str,
        *,
        reason: str | None = None,
    ) -> tuple[LifecycleEvent, list[HookResult]]:
        """Emit a normalized stage transition event."""

        event = new_event(
            cast(EventType, event_type),
            stage_id=stage_id,
            actor_type="core",
            actor_id="state-manager",
            payload={"project_id": state.project_id, "reason": reason},
        )
        results = self.emit(event)
        return event, results
