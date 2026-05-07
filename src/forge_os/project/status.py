"""Read-only project status helpers."""

import json
from pathlib import Path

from pydantic import ValidationError

from forge_os.config.loader import ConfigError, load_config
from forge_os.context.registry import ArtifactRegistry, ArtifactRegistryError
from forge_os.project.detect import find_project_root
from forge_os.schemas.config import ForgeConfig
from forge_os.schemas.state import PipelineState


class StateError(RuntimeError):
    """Raised when state cannot be loaded or validated."""


def load_state(project_root: Path) -> PipelineState:
    """Load and validate `.forge/state.json`."""

    path = project_root / ".forge" / "state.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StateError(f"Could not read state file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise StateError(f"State file is not valid JSON: {path}") from exc

    try:
        return PipelineState.model_validate(raw)
    except ValidationError as exc:
        raise StateError(str(exc)) from exc


def read_project_status(start: Path | None = None) -> tuple[Path, ForgeConfig, PipelineState]:
    """Return project root, config, and state for read-only status output."""

    root = find_project_root(start)
    try:
        config = load_config(root / ".forge" / "config.yaml")
    except ConfigError:
        raise
    state = load_state(root)
    return root, config, state


def stale_artifact_count(project_root: Path) -> int:
    """Return count of known stale artifacts, tolerating missing Phase 07 files."""

    try:
        return ArtifactRegistry(project_root).stale_count()
    except ArtifactRegistryError:
        return 0


def next_action_for(state: PipelineState) -> str:
    """Return a Phase 01 next-action hint without enforcing transitions."""

    if state.current_stage_id is None:
        return "No active stage. Review project state before continuing."
    return f"Work on the `{state.current_stage_id}` stage, then run `forge stage advance`."
