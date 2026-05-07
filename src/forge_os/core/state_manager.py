"""Deterministic Phase 02 pipeline state manager."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from forge_os.config.loader import ConfigError, load_config
from forge_os.events.bus import EventBus
from forge_os.gates.coordinator import GateCoordinator
from forge_os.gates.models import GateResult
from forge_os.hooks.registry import HookRegistry
from forge_os.project.status import StateError, load_state
from forge_os.schemas.config import ForgeConfig
from forge_os.schemas.state import PipelineState, StageState


class StateTransitionError(RuntimeError):
    """Raised when a requested state transition is invalid."""


class AtomicWriteError(RuntimeError):
    """Raised when atomic persistence fails."""


def utc_now() -> str:
    """Return an RFC 3339 UTC timestamp."""

    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


class StateManager:
    """Read, validate, transition, and persist Forge pipeline state."""

    def __init__(self, project_root: Path, hook_registry: HookRegistry | None = None) -> None:
        self.project_root: Path = project_root.resolve()
        self.forge_dir: Path = self.project_root / ".forge"
        self.pipeline_dir: Path = self.project_root / "pipeline"
        self.state_path: Path = self.forge_dir / "state.json"
        self.events_path: Path = self.forge_dir / "events.jsonl"
        self.state_markdown_path: Path = self.pipeline_dir / "state.md"
        self.event_bus: EventBus = EventBus(self.events_path, hook_registry)

    @classmethod
    def for_project(
        cls,
        project_root: Path,
        hook_registry: HookRegistry | None = None,
    ) -> StateManager:
        """Create a manager for a project root."""

        return cls(project_root, hook_registry)

    def load_config(self) -> ForgeConfig:
        """Load project config."""

        try:
            return load_config(self.forge_dir / "config.yaml")
        except ConfigError:
            raise

    def load(self) -> PipelineState:
        """Load validated pipeline state."""

        try:
            return load_state(self.project_root)
        except StateError:
            raise

    def save(self, state: PipelineState) -> None:
        """Persist state atomically and sync the human-readable markdown mirror."""

        state.updated_at = utc_now()
        self._atomic_write_text(self.state_path, self._dump_json(state.model_dump()))
        config = self.load_config()
        self._atomic_write_text(self.state_markdown_path, self.render_state_markdown(config, state))

    def list_stages(self) -> list[StageState]:
        """Return stage states in configured order."""

        return self.load().stages

    def start_stage(self, stage_id: str) -> PipelineState:
        """Start a not-yet-started stage when deterministic transition rules allow it."""

        state = self.load()
        index = self._stage_index(state, stage_id)
        stage = state.stages[index]

        if stage.status == "active":
            raise StateTransitionError(f"Stage `{stage_id}` is already active.")
        if stage.status == "complete":
            raise StateTransitionError(f"Stage `{stage_id}` is already complete.")
        if any(candidate.status == "active" for candidate in state.stages):
            raise StateTransitionError(
                "Another stage is already active. Complete it before starting a new stage."
            )
        if index > 0 and state.stages[index - 1].status != "complete":
            previous = state.stages[index - 1].stage_id
            raise StateTransitionError(f"Previous stage `{previous}` must be complete first.")

        stage.status = "active"
        stage.entered_at = stage.entered_at or utc_now()
        stage.blocked_reason = None
        state.current_stage_id = stage.stage_id
        self.save(state)
        self.log_transition("StageStarted", state, stage.stage_id)
        return state

    def complete_stage(self, stage_id: str) -> PipelineState:
        """Complete an active stage."""

        state = self.load()
        stage = self._stage(state, stage_id)
        if stage.status != "active":
            raise StateTransitionError(f"Stage `{stage_id}` must be active before it can complete.")

        gate_results = self._evaluate_gates_for_stage(state, stage_id)
        if any(result.blocking for result in gate_results):
            stage.status = "blocked"
            stage.blocked_reason = self._gate_block_reason(gate_results)
            self.save(state)
            self.log_transition("StageBlocked", state, stage.stage_id)
            raise StateTransitionError(stage.blocked_reason)

        stage.status = "complete"
        stage.completed_at = utc_now()
        stage.blocked_reason = None
        state.current_stage_id = None
        self.save(state)
        self.log_transition("StageCompleted", state, stage.stage_id)
        return state

    def advance(self) -> PipelineState:
        """Advance from the current active stage to the next deterministic stage."""

        state = self.load()
        current_id = state.current_stage_id
        if current_id is None:
            next_stage = self._first_not_started_stage(state)
            if next_stage is None:
                raise StateTransitionError("Pipeline is already complete.")
            return self.start_stage(next_stage.stage_id)

        current_index = self._stage_index(state, current_id)
        current_stage = state.stages[current_index]
        if current_stage.status != "active":
            raise StateTransitionError(f"Current stage `{current_id}` is not active.")

        _ = self.complete_stage(current_id)
        next_index = current_index + 1
        if next_index >= len(state.stages):
            completed_state = self.load()
            completed_state.current_stage_id = None
            self.save(completed_state)
            return completed_state
        return self.start_stage(state.stages[next_index].stage_id)

    def override_stage(self, stage_id: str, *, reason: str) -> PipelineState:
        """Force the active stage with a required audit reason."""

        if not reason.strip():
            raise StateTransitionError("Override requires a non-empty reason.")

        state = self.load()
        target = self._stage(state, stage_id)
        timestamp = utc_now()
        for stage in state.stages:
            if stage.stage_id == target.stage_id:
                stage.status = "active"
                stage.entered_at = stage.entered_at or timestamp
                stage.blocked_reason = None
            elif stage.status == "active":
                stage.status = "blocked"
                stage.blocked_reason = f"Superseded by override to `{target.stage_id}`."
        state.current_stage_id = target.stage_id
        self.save(state)
        self.log_transition("StageOverride", state, target.stage_id, reason=reason.strip())
        return state

    def log_transition(
        self,
        event_type: str,
        state: PipelineState,
        stage_id: str,
        *,
        reason: str | None = None,
    ) -> None:
        """Append a normalized transition event to `.forge/events.jsonl` and run hooks."""

        event, _hook_results = self.event_bus.emit_transition(
            event_type,
            state,
            stage_id,
            reason=reason,
        )
        state.last_event_id = event.event_id
        self._atomic_write_text(self.state_path, self._dump_json(state.model_dump()))

    def render_state_markdown(self, config: ForgeConfig, state: PipelineState) -> str:
        """Render the human-readable state mirror."""

        current = state.current_stage_id or "none"
        lines = [
            "# Forge Pipeline State",
            "",
            "This file is generated from `.forge/state.json`. Do not treat it as canonical.",
            "",
            f"- Project: {config.project.name}",
            f"- Profile: {config.profile}",
            f"- State schema version: {state.schema_version}",
            f"- Current stage: {current}",
            f"- Updated at: {state.updated_at}",
            "",
            "## Stages",
            "",
        ]
        lines.extend(f"- {stage.stage_id}: {stage.status}" for stage in state.stages)
        lines.append("")
        return "\n".join(lines)

    def _atomic_write_text(self, path: Path, content: str) -> None:
        """Write text through a temp file and atomic replace."""

        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.tmp-{uuid4()}")
        try:
            _ = temp_path.write_text(content, encoding="utf-8")
            os.replace(temp_path, path)
        except OSError as exc:
            if temp_path.exists():
                temp_path.unlink()
            raise AtomicWriteError(f"Failed to atomically write {path}") from exc

    def _dump_json(self, data: object) -> str:
        return json.dumps(data, indent=2, sort_keys=False) + "\n"

    def _stage(self, state: PipelineState, stage_id: str) -> StageState:
        for stage in state.stages:
            if stage.stage_id == stage_id:
                return stage
        raise StateTransitionError(f"Unknown stage `{stage_id}`.")

    def _stage_index(self, state: PipelineState, stage_id: str) -> int:
        for index, stage in enumerate(state.stages):
            if stage.stage_id == stage_id:
                return index
        raise StateTransitionError(f"Unknown stage `{stage_id}`.")

    def _first_not_started_stage(self, state: PipelineState) -> StageState | None:
        for stage in state.stages:
            if stage.status == "not_started":
                return stage
        return None

    def _evaluate_gates_for_stage(self, state: PipelineState, stage_id: str) -> list[GateResult]:
        """Evaluate Phase 04 gates and persist latest results in state."""

        coordinator = GateCoordinator(self.project_root, self.event_bus)
        results = coordinator.evaluate_stage(stage_id)
        state.gates[stage_id] = {
            "blocked": coordinator.has_blocking_failures(results),
            "results": [result.model_dump() for result in results],
        }
        return results

    def _gate_block_reason(self, results: list[GateResult]) -> str:
        blocking = [result for result in results if result.blocking]
        if not blocking:
            return "Gate evaluation blocked this stage."
        return "; ".join(result.summary for result in blocking)


def validate_state_file(path: Path) -> PipelineState:
    """Validate a state file after persistence; useful for tests and future recovery."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return PipelineState.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise StateError(f"Invalid state file: {path}") from exc
