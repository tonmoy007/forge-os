"""In-process lifecycle event bus."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from forge_os.events.log import append_event
from forge_os.events.model import EventType, LifecycleEvent, new_event
from forge_os.hooks.registry import HookRegistry, HookResult
from forge_os.hooks.timing import HookTiming, HookTimingLog
from forge_os.schemas.state import PipelineState


class EventBus:
    """Append normalized events and dispatch in-process hooks."""

    def __init__(self, event_log_path: Path, hook_registry: HookRegistry | None = None) -> None:
        self.event_log_path: Path = event_log_path
        self.hook_registry: HookRegistry = hook_registry or HookRegistry()

    def emit(self, event: LifecycleEvent) -> list[HookResult]:
        """Append an event and dispatch hooks in deterministic order."""

        append_event(self.event_log_path, event)
        results = self.hook_registry.run(event)
        self._record_timings(event.event_type, results)
        return results

    def _record_timings(self, event_type: str, results: list[HookResult]) -> None:
        """Persist hook latencies for FR-HD-005, best-effort.

        Only writes when hooks actually ran, and never raises into ``emit`` — hook
        timing is observability, not part of the event/state write path.
        """

        if not results:
            return
        try:
            timings = [
                HookTiming(
                    event_type=event_type,
                    hook_name=result.hook_name,
                    status=result.status,
                    duration_ms=result.duration_ms,
                )
                for result in results
            ]
            HookTimingLog(self.event_log_path.parent).append(timings)
        except Exception:  # noqa: BLE001 - recording must never break a state mutation
            pass

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
