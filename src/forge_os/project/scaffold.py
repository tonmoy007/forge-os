"""Project scaffolding for Phase 01."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

import yaml

from forge_os.adapters.registry import ADAPTER_PRIORITY, adapter_placeholder_config
from forge_os.project.profiles import build_gate_document, build_stage_document, get_profile_stages
from forge_os.schemas.config import (
    SUPPORTED_PROFILES,
    ForgeConfig,
    HooksConfig,
    ProjectConfig,
    SecurityConfig,
)
from forge_os.schemas.state import PipelineState, StageState


class ProjectAlreadyInitializedError(RuntimeError):
    """Raised when attempting to initialize an existing Forge project."""


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _write_text(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ProjectAlreadyInitializedError(f"Refusing to overwrite existing file: {path}")
    _ = path.write_text(content, encoding="utf-8")


def _yaml_dump(data: object) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def _json_dump(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=False) + "\n"


def _build_config(
    project_name: str,
    profile: str,
    default_adapter: str = "dummy",
    adapter_options: dict[str, object] | None = None,
) -> ForgeConfig:
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"Unsupported profile: {profile}")
    if default_adapter not in ADAPTER_PRIORITY:
        choices = ", ".join(ADAPTER_PRIORITY)
        raise ValueError(f"Unsupported adapter: {default_adapter}. Choose one of: {choices}")

    adapters = adapter_placeholder_config()
    # Exactly the chosen default is enabled (the placeholder enables dummy).
    adapters["dummy"]["enabled"] = default_adapter == "dummy"
    adapters[default_adapter]["enabled"] = True
    if adapter_options:
        adapters[default_adapter].update(adapter_options)

    validated_profile = cast(Literal["minimal", "standard", "expert"], profile)
    return ForgeConfig(
        schema_version="0.1",
        project=ProjectConfig(name=project_name, root_policy="project_only"),
        profile=validated_profile,
        default_adapter=default_adapter,
        adapters=adapters,
        security=SecurityConfig(profile="baseline"),
        hooks=HooksConfig(enabled=False),
        features={
            "daemon": False,
            "channels": False,
            "openclaw": False,
            "plugins": False,
        },
    )


def _build_state(profile: str) -> PipelineState:
    timestamp = _now()
    stages = get_profile_stages(profile)
    return PipelineState(
        schema_version="0.1",
        project_id=f"forge-{uuid4()}",
        profile=profile,
        current_stage_id=stages[0].id if stages else None,
        stages=[
            StageState(
                stage_id=stage.id,
                status="active" if index == 0 else "not_started",
                entered_at=timestamp if index == 0 else None,
            )
            for index, stage in enumerate(stages)
        ],
        gates={},
        last_event_id=None,
        created_at=timestamp,
        updated_at=timestamp,
        metadata={"created_by": "forge init"},
    )


def _state_markdown(config: ForgeConfig, state: PipelineState) -> str:
    current = state.current_stage_id or "none"
    return (
        "# Forge Pipeline State\n\n"
        "This file is a human-readable mirror generated from Forge OS machine state. "
        "Do not treat it as the canonical source of truth.\n\n"
        f"- Project: {config.project.name}\n"
        f"- Profile: {config.profile}\n"
        f"- State schema version: {state.schema_version}\n"
        f"- Current stage: {current}\n\n"
        "## Stages\n\n"
        + "\n".join(f"- {stage.stage_id}: {stage.status}" for stage in state.stages)
        + "\n"
    )


def initialize_project(
    root: Path,
    *,
    project_name: str,
    profile: str = "minimal",
    default_adapter: str = "dummy",
    adapter_options: dict[str, object] | None = None,
    overwrite: bool = False,
) -> Path:
    """Create a Forge project scaffold under `root`.

    ``default_adapter`` selects the kernel adapter written to config.yaml
    (P055.15); the chosen adapter is marked ``enabled`` and ``adapter_options``
    (e.g. ``permission_mode`` for claude_code) are merged into its config.
    """

    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"Unsupported profile: {profile}")

    if (root / ".forge").exists() and not overwrite:
        raise ProjectAlreadyInitializedError(
            f"Forge project already exists at {root}. Use --force to overwrite Phase 01 files."
        )

    config = _build_config(project_name, profile, default_adapter, adapter_options)
    state = _build_state(profile)

    for directory in (
        root / ".forge",
        root / ".forge" / "reflections",
        root / ".forge" / "agents",
        root / ".forge" / "agents" / "personas",
        root / ".forge" / "agents" / "contracts",
        root / "pipeline",
        root / "pipeline" / "decisions",
        root / "pipeline" / "log",
        root / "tasks",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    _write_text(
        root / ".forge" / "config.yaml",
        _yaml_dump(config.model_dump()),
        overwrite=overwrite,
    )
    _write_text(
        root / ".forge" / "state.json",
        _json_dump(state.model_dump()),
        overwrite=overwrite,
    )
    _write_text(root / ".forge" / "events.jsonl", "", overwrite=overwrite)
    _write_text(root / ".forge" / "session-log.jsonl", "", overwrite=overwrite)
    _write_text(root / ".forge" / "agent-runs.jsonl", "", overwrite=overwrite)
    _write_text(root / ".forge" / "context-selections.jsonl", "", overwrite=overwrite)
    _write_text(root / ".forge" / "hook-timings.jsonl", "", overwrite=overwrite)
    _write_text(root / ".forge" / "security-audit.jsonl", "", overwrite=overwrite)
    _write_text(
        root / ".forge" / "lessons.yaml",
        _yaml_dump({"schema_version": "0.1", "lessons": []}),
        overwrite=overwrite,
    )
    _write_text(root / ".forge" / "patterns.jsonl", "", overwrite=overwrite)
    _write_text(
        root / ".forge" / "artifacts.json",
        _json_dump({"schema_version": "0.1", "artifacts": []}),
        overwrite=overwrite,
    )
    _write_text(
        root / ".forge" / "adg.json",
        _json_dump({"schema_version": "0.1", "nodes": [], "edges": []}),
        overwrite=overwrite,
    )
    _write_text(root / "pipeline" / "state.md", _state_markdown(config, state), overwrite=overwrite)
    _write_text(
        root / "pipeline" / "stages.yaml",
        _yaml_dump(build_stage_document(profile)),
        overwrite=overwrite,
    )
    _write_text(
        root / "pipeline" / "gates.yaml",
        _yaml_dump(build_gate_document(profile)),
        overwrite=overwrite,
    )
    _write_text(
        root / "tasks" / "README.md",
        "# Forge Tasks\n\nUse this directory for task plans and implementation notes.\n",
        overwrite=overwrite,
    )

    return root
