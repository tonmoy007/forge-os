"""State machine health checker."""

from __future__ import annotations

from pathlib import Path

from forge_os.health.checker import HealthChecker, HealthResult
from forge_os.project.status import load_state


class StateHealthChecker(HealthChecker):
    """Check state machine health: file integrity, transition count, last transition."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def check(self) -> HealthResult:
        state_path = self.project_root / ".forge" / "state.json"
        if not state_path.exists():
            return HealthResult(
                healthy=False,
                message="state.json not found. Run forge init first.",
                recommendations=["Run `forge init --path .` to initialize the project."],
            )

        try:
            state = load_state(self.project_root)
        except Exception as exc:
            return HealthResult(
                healthy=False,
                message=f"Failed to load state: {exc}",
                recommendations=["Run `forge stage override` to repair state, or re-init."],
            )

        completed = sum(1 for s in state.stages if s.status == "complete")
        total = len(state.stages)

        details = {
            "project_id": state.project_id,
            "profile": state.profile,
            "current_stage": state.current_stage_id,
            "stages_completed": completed,
            "stages_total": total,
            "last_event_id": state.last_event_id,
        }

        return HealthResult(
            healthy=True,
            message=f"State machine healthy. {completed}/{total} stages completed.",
            details=details,
        )
