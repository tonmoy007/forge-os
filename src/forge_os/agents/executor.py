"""Phase 05 stage-agent execution orchestration.

Phase 08.5 adds async variant `run_stage_agent_async`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import uuid4

from forge_os.adapters.registry import AdapterRegistryError, create_adapter_from_config
from forge_os.agents.loader import AgentLoadError, contract_for_persona, persona_for_stage
from forge_os.agents.models import AgentRunRecord, OutputContract, validate_contract
from forge_os.config.loader import ConfigError
from forge_os.context.lazy import LazyContextBuilder, LazyContextError
from forge_os.context.pruner import ContextPruner, ContextPrunerError
from forge_os.context.registry import ArtifactRegistry, ArtifactRegistryError
from forge_os.context.token_monitor import evaluate_session_budget, resolve_warn_ratio
from forge_os.core.state_manager import utc_now
from forge_os.events.model import new_event
from forge_os.memory.lessons import LessonStore
from forge_os.schemas.state import PipelineState

log = logging.getLogger("forge.agents.executor")


class AgentExecutionError(RuntimeError):
    """Raised when a stage agent cannot be executed successfully."""


def run_stage_agent(
    project_root: Path,
    state: PipelineState,
    stage_id: str,
    *,
    forge_dir: Path | None = None,
) -> AgentRunRecord:
    """Spawn the configured stage agent and persist a normalized run record.

    `forge_dir` (L001/L005) reaches the lazy-context skill reader; default None
    means the real `~/.forge`.
    """

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
    _monitor_token_budget(project_root, stage_id, context_selection)
    context = _stage_context(
        project_root,
        state,
        stage_id,
        approved_lessons,
        context_selection.model_dump(),
        contract,
        forge_dir=forge_dir,
    )
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
    project_root: Path,
    state: PipelineState,
    stage_id: str,
    approved_lessons: list[dict[str, object]],
    context_selection: dict[str, object],
    contract: OutputContract,
    *,
    forge_dir: Path | None = None,
) -> str:
    # The contract's required outputs MUST reach the agent: a real kernel only
    # knows which files to produce from this context (the deterministic
    # DummyAdapter fabricated its own outputs, which masked the gap — found by
    # the Phase 05.5 kill-criterion run).

    # Phase 10 WS-D: lazy context (skill menu + lesson index) must never break
    # an agent spawn, but failures must stay visible in the log and payload.
    try:
        lazy_context: dict[str, object] = (
            LazyContextBuilder(project_root, forge_dir=forge_dir)
            .build(stage_id, token_budget=2000)
            .model_dump()
        )
    except (LazyContextError, OSError) as exc:
        log.warning("Lazy context build failed for stage %s: %s", stage_id, exc)
        lazy_context = {"skills_menu": [], "lesson_index": [], "error": str(exc)}
    return json.dumps(
        {
            "project_id": state.project_id,
            "profile": state.profile,
            "current_stage_id": state.current_stage_id,
            "stage_id": stage_id,
            # Stage runs are unattended; adapters render this for their kernel
            # (e.g. ClaudeCodeAdapter's batch execution directive).
            "execution_mode": "batch",
            "approved_lessons": approved_lessons,
            "selected_context": context_selection,
            "lazy_context": lazy_context,
            "required_outputs": [
                {
                    "path": requirement.path,
                    "type": requirement.type,
                    "description": requirement.description,
                    "blocking": requirement.blocking,
                }
                for requirement in contract.required_outputs
            ],
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


def _monitor_token_budget(project_root: Path, stage_id: str, selection: object) -> None:
    """Grade the stage's injected-context budget; log + record an event on overage.

    Best-effort observability (FR-HD-003 / FR-TE-003): it must NEVER break a spawn,
    so a missing config or an event-write failure degrades to a log line.
    """
    from forge_os.config.loader import load_config
    from forge_os.events.log import append_event

    try:
        features = load_config(project_root / ".forge" / "config.yaml").features
    except Exception as exc:  # noqa: BLE001 — best-effort: a degraded config must never break a spawn
        # load_config can raise EITHER config.loader.ConfigError (RuntimeError) OR a
        # validator-raised schemas.config.ConfigError (a plain Exception, NOT wrapped in
        # ValidationError) — plus OSError. A narrow catch misses one and aborts the
        # async spawn (where this is the only config load). See L011.
        log.warning("Token monitor could not load config for stage %s: %s", stage_id, exc)
        features = {}

    total_tokens = getattr(selection, "total_tokens", 0)
    token_budget = getattr(selection, "token_budget", 0)
    evaluation = evaluate_session_budget(
        total_tokens, token_budget, warn_ratio=resolve_warn_ratio(features)
    )
    if evaluation.level == "ok":
        return

    log.warning(
        "Injected-context token budget %s for stage %s: %d/%d tokens (%.0f%%)",
        evaluation.level,
        stage_id,
        evaluation.total_tokens,
        evaluation.token_budget,
        evaluation.ratio * 100,
    )
    event = new_event(
        "TokenBudgetExceeded",
        stage_id=stage_id,
        actor_type="core",
        actor_id="context-pruner",
        payload={
            "level": evaluation.level,
            "total_tokens": evaluation.total_tokens,
            "token_budget": evaluation.token_budget,
            "ratio": round(evaluation.ratio, 4),
            "selection_id": getattr(selection, "selection_id", None),
        },
    )
    try:
        append_event(project_root / ".forge" / "events.jsonl", event)
    except OSError as exc:
        log.warning("Failed to record TokenBudgetExceeded event for stage %s: %s", stage_id, exc)


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


# ── Async Variant (Phase 08.5) ─────────────────────────────────────────────


async def run_stage_agent_async(
    project_root: Path,
    state: PipelineState,
    stage_id: str,
    *,
    forge_dir: Path | None = None,
) -> AgentRunRecord:
    """Async variant of run_stage_agent. Uses AsyncDummyAdapter when configured.

    Follows the same logic as the sync version but delegates to async adapters.
    Currently supports AsyncDummyAdapter; more async adapter targets added per
    Phase 08.5 workstream A.
    """
    from forge_os.adapters.async_dummy import AsyncDummyAdapter

    try:
        persona = persona_for_stage(project_root, stage_id)
        contract = contract_for_persona(project_root, persona)
    except (AgentLoadError, AdapterRegistryError, ConfigError) as exc:
        raise AgentExecutionError(str(exc)) from exc

    started_at = utc_now()
    approved_lessons = LessonStore(project_root).render_context(stage_id=stage_id)
    try:
        context_selection = ContextPruner(project_root).select(stage_id, token_budget=2000)
    except ContextPrunerError as exc:
        raise AgentExecutionError(str(exc)) from exc
    _monitor_token_budget(project_root, stage_id, context_selection)
    context = _stage_context(
        project_root,
        state,
        stage_id,
        approved_lessons,
        context_selection.model_dump(),
        contract,
        forge_dir=forge_dir,
    )
    tools = persona.default_tools or []

    # Use AsyncDummyAdapter. In future phases this routes to the configured
    # async adapter via an async adapter registry.
    adapter = AsyncDummyAdapter(project_root, create_outputs=True)
    try:
        handle = await adapter.spawn_agent(persona, context, tools)
    except AdapterRegistryError as exc:
        raise AgentExecutionError(str(exc)) from exc

    validation = validate_contract(project_root, contract)
    completed_at = utc_now()
    status = (
        "completed" if validation.passed and handle.status == "completed" else "contract_failed"
    )
    record = AgentRunRecord(
        run_id=f"async-run-{uuid4()}",
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
            "async": True,
        },
    )
    _register_agent_outputs(project_root, stage_id, [output.path for output in handle.outputs])
    _append_agent_record(project_root, record)
    _append_agent_event(project_root, record)

    if not validation.passed:
        summaries = "; ".join(check.summary for check in validation.checks if not check.passed)
        raise AgentExecutionError(summaries or f"Output contract `{contract.id}` failed.")
    return record
