"""Phase 05 stage-agent execution orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from forge_os.adapters.registry import AdapterRegistryError, create_adapter_from_config
from forge_os.agents.loader import AgentLoadError, contract_for_persona, persona_for_stage
from forge_os.agents.models import AgentRunRecord, validate_contract
from forge_os.config.loader import ConfigError
from forge_os.context.pruner import ContextPruner, ContextPrunerError
from forge_os.context.registry import ArtifactRegistry, ArtifactRegistryError
from forge_os.core.state_manager import utc_now
from forge_os.events.model import new_event
from forge_os.memory.lessons import LessonStore
from forge_os.schemas.state import PipelineState


class AgentExecutionError(RuntimeError):
    """Raised when a stage agent cannot be executed successfully."""


def run_stage_agent(project_root: Path, state: PipelineState, stage_id: str) -> AgentRunRecord:
    """Spawn the configured stage agent and persist a normalized run record."""

    try:
        from forge_os.config.loader import load_config

        config = load_config(project_root / ".forge" / "config.yaml")
        persona = persona_for_stage(project_root, stage_id)
        contract = contract_for_persona(project_root, persona)
        adapter = create_adapter_from_config(project_root, config)
    except (AgentLoadError, AdapterRegistryError, ConfigError) as exc:
        raise AgentExecutionError(str(exc)) from exc

    started_at = utc_now()
    approved_lessons = LessonStore(project_root).render_context(stage_id=stage_id)
    try:
        context_selection = ContextPruner(project_root).select(stage_id, token_budget=2000)
    except ContextPrunerError as exc:
        raise AgentExecutionError(str(exc)) from exc
    context = _stage_context(state, stage_id, approved_lessons, context_selection.model_dump())
    tools = persona.default_tools or adapter.get_default_tools()
    try:
        handle = adapter.spawn_agent(persona, context, tools)
    except AdapterRegistryError as exc:
        raise AgentExecutionError(str(exc)) from exc
    validation = validate_contract(project_root, contract)
    completed_at = utc_now()
    status = (
        "completed" if validation.passed and handle.status == "completed" else "contract_failed"
    )
    record = AgentRunRecord(
        run_id=f"run-{uuid4()}",
        adapter=handle.provider,
        handle_id=handle.handle_id,
        persona_id=persona.id,
        stage_id=stage_id,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        outputs=handle.outputs,
        contract=validation,
        metadata={
            "adapter_metadata": handle.metadata,
            "approved_lessons": approved_lessons,
            "context_selection_id": context_selection.selection_id,
            "context_total_tokens": context_selection.total_tokens,
            "context_paths": [item.path for item in context_selection.selected],
        },
    )
    _register_agent_outputs(project_root, stage_id, [output.path for output in handle.outputs])
    _append_agent_record(project_root, record)
    _append_agent_event(project_root, record)

    if not validation.passed:
        summaries = "; ".join(check.summary for check in validation.checks if not check.passed)
        raise AgentExecutionError(summaries or f"Output contract `{contract.id}` failed.")
    return record


def _stage_context(
    state: PipelineState,
    stage_id: str,
    approved_lessons: list[dict[str, object]],
    context_selection: dict[str, object],
) -> str:
    return json.dumps(
        {
            "project_id": state.project_id,
            "profile": state.profile,
            "current_stage_id": state.current_stage_id,
            "stage_id": stage_id,
            "approved_lessons": approved_lessons,
            "selected_context": context_selection,
        },
        sort_keys=True,
    )


def _register_agent_outputs(project_root: Path, stage_id: str, output_paths: list[str]) -> None:
    try:
        _ = ArtifactRegistry(project_root).register_stage_outputs(stage_id, output_paths)
    except ArtifactRegistryError as exc:
        raise AgentExecutionError(str(exc)) from exc


def _append_agent_record(project_root: Path, record: AgentRunRecord) -> None:
    log_path = project_root / ".forge" / "agent-runs.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        _ = log_file.write(json.dumps(record.model_dump(), sort_keys=False) + "\n")


def _append_agent_event(project_root: Path, record: AgentRunRecord) -> None:
    from forge_os.events.log import append_event

    event = new_event(
        "SubagentStop",
        stage_id=record.stage_id,
        actor_type="adapter",
        actor_id=record.adapter,
        payload={
            "run_id": record.run_id,
            "persona_id": record.persona_id,
            "status": record.status,
            "contract_passed": record.contract.passed if record.contract else None,
        },
    )
    append_event(project_root / ".forge" / "events.jsonl", event)
