"""Forge OS CLI — Clean Code Architecture.

All CLI commands delegate to the use_cases layer. CLI code handles only:
- Typer argument/option parsing
- Output formatting (Rich tables, console)
- Error translation (domain exceptions → user-facing messages)

Business logic lives in use_cases/ and project/ modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from forge_os import __version__
from forge_os.adapters.claude_code.runner import (
    ClaudeCodeSpawnError,
    get_claude_version,
    validate_permission_mode,
)
from forge_os.adapters.registry import (
    ADAPTER_CLASS_NAMES,
    ADAPTER_PRIORITY,
    AdapterRegistryError,
)
from forge_os.agents.executor import AgentExecutionError, run_stage_agent
from forge_os.agents.loader import AgentLoadError, load_contracts, load_personas

# Phase 08+ sub-apps (imported from commands/ sub-modules)
from forge_os.cli.commands.acp import acp_app
from forge_os.cli.commands.backtrack import backtrack_app
from forge_os.cli.commands.channel import channel_app
from forge_os.cli.commands.cost import cost_app
from forge_os.cli.commands.daemon import daemon_app
from forge_os.cli.commands.doctor import doctor_app
from forge_os.cli.commands.dreamer import dreamer_app
from forge_os.cli.commands.health import health_app
from forge_os.cli.commands.lazy_context import lazy_budget, lazy_stats
from forge_os.cli.commands.plug import plug_app
from forge_os.cli.commands.security import security_app
from forge_os.config.loader import ConfigError, load_config
from forge_os.context.pruner import ContextPruner, ContextPrunerError
from forge_os.context.registry import ArtifactRegistry, ArtifactRegistryError
from forge_os.core import StateError, StateManager, StateTransitionError
from forge_os.events.log import EventLogError, filter_events, read_events
from forge_os.gates import GateCoordinator, GateLoadError
from forge_os.memory.lessons import LessonStore, LessonStoreError
from forge_os.memory.reflections import ReflectionStore, ReflectionStoreError
from forge_os.project.detect import ProjectNotFoundError, find_project_root
from forge_os.project.scaffold import ProjectAlreadyInitializedError, initialize_project
from forge_os.project.status import (
    daemon_alerts,
    next_action_for,
    read_project_status,
    stale_artifact_count,
)
from forge_os.schemas.config import SUPPORTED_PROFILES
from forge_os.use_cases.adapters import AdapterUseCases

# ─── Console & App Structure ───────────────────────────────────────────────────

console = Console()

app = typer.Typer(no_args_is_help=True, help="Forge OS local-first lifecycle CLI.")
config_app = typer.Typer(help="Inspect and validate Forge project configuration.")
stage_app = typer.Typer(help="Inspect and transition Forge pipeline stages.")
events_app = typer.Typer(help="Inspect normalized lifecycle events.")
gate_app = typer.Typer(help="Inspect and evaluate Forge gates.")
adapter_app = typer.Typer(help="Inspect configured kernel adapters.")
agent_app = typer.Typer(help="Inspect and run Forge agent personas.")
lesson_app = typer.Typer(help="Manage project lessons and approval workflow.")
reflection_app = typer.Typer(help="Inspect stored lifecycle reflections.")
artifact_app = typer.Typer(help="Manage registered artifacts and the ADG.")
context_app = typer.Typer(help="Select deterministic pruned agent context.")

app.add_typer(config_app, name="config")
app.add_typer(stage_app, name="stage")
app.add_typer(events_app, name="events")
app.add_typer(gate_app, name="gate")
app.add_typer(adapter_app, name="adapter")
app.add_typer(agent_app, name="agent")
app.add_typer(lesson_app, name="lesson")
app.add_typer(reflection_app, name="reflection")
app.add_typer(artifact_app, name="artifact")
app.add_typer(context_app, name="context")
# Phase 10 lazy-context commands surface under the existing `context` group.
context_app.command("budget")(lazy_budget)
context_app.command("lazy-stats")(lazy_stats)
app.add_typer(backtrack_app, name="backtrack")
app.add_typer(security_app, name="security")
app.add_typer(health_app, name="health")
app.add_typer(acp_app, name="acp")
app.add_typer(dreamer_app, name="dreamer")
app.add_typer(daemon_app, name="daemon")
app.add_typer(doctor_app, name="doctor")
app.add_typer(cost_app, name="cost")
# Phase 11 extension management + channels
app.add_typer(plug_app, name="plug")
app.add_typer(channel_app, name="channel")

# ─── Explain Topics ────────────────────────────────────────────────────────────

EXPLAIN_TOPICS: dict[str, str] = {
    "phase-01": (
        "Phase 01 provides local CLI scaffolding only: init, status, config show, "
        "config validate, and explain. It intentionally avoids agents, real gates, "
        "state transitions, memory, ADG, daemon, channels, OpenClaw, and plugins."
    ),
    "state": (
        "`.forge/state.json` is the canonical machine-readable state file. "
        "`pipeline/state.md` is a human-readable mirror and should not be treated as "
        "source of truth."
    ),
    "config": (
        "`.forge/config.yaml` stores local project configuration. Phase 01 validates the "
        "schema, profile, default adapter, hooks flag, and baseline security skeleton."
    ),
    "profiles": "Built-in Phase 01 profiles are `minimal`, `standard`, and `expert`.",
    "security": (
        "Phase 01 uses secure defaults: local-only operation, no provider credentials, "
        "hooks disabled, no arbitrary command execution, and no network requirement. "
        "Phase 08 adds YAML-defined security profiles with path restrictions, command "
        "allowlists, timeouts, and an append-only `.forge/security-audit.jsonl` log."
    ),
    "stage": (
        "Phase 02 stage commands support deterministic list, start, complete, advance, "
        "and override operations. Overrides require an audit reason."
    ),
    "events": (
        "Phase 03 events are normalized JSONL records stored in `.forge/events.jsonl`. "
        "Use `forge events list` or `forge events tail` to inspect them."
    ),
    "gates": (
        "Phase 04 gates evaluate deterministic file and pattern criteria. "
        "Blocking failures prevent stage completion/advance."
    ),
    "adapters": (
        "Phase 05 adapters implement the KernelAdapter portability boundary. "
        "The deterministic DummyAdapter is available now; real provider adapters "
        "remain placeholders."
    ),
    "agents": (
        "Phase 05 agents are open-format personas with deterministic output contracts. "
        "Use `forge agent list` and `forge agent run` to inspect or execute them."
    ),
    "lessons": (
        "Phase 06 lessons are project-local YAML records. Pending lessons require approval "
        "before they are injected into future agent context."
    ),
    "reflections": (
        "Phase 06 reflections are structured YAML files under `.forge/reflections/`, "
        "captured after lifecycle milestones for lesson review."
    ),
    "artifacts": (
        "Phase 07 artifacts are registered project-relative files with explicit "
        "dependencies and freshness metadata."
    ),
    "context": (
        "Phase 07 context selection traverses the artifact dependency graph and prunes "
        "selected files under a deterministic token budget."
    ),
    "backtrack": (
        "Phase 08 backtrack tickets track rework requests. Use `forge backtrack list` "
        "to see tickets and `forge backtrack plan <id>` to see the affected cascade."
    ),
    "acp": (
        "Phase 08 ACP integration lets Forge OS discover and spawn ACP-compatible agents "
        "from the official registry. Use `forge acp discover` to list available agents."
    ),
    "health": (
        "Phase 09 health checks cover all subsystems: state machine, gates, ADG, memory, "
        "and ACP agents. Use `forge health check` for a full report."
    ),
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_project_root(path: Path | None) -> Path:
    return find_project_root((path or Path.cwd()).resolve())


def _resolve_project_status(
    path: Path | None,
) -> tuple[Path, object, object]:
    """Return (root, config, state) for a project at *path*."""
    return read_project_status((path or Path.cwd()).resolve())


def _state_manager_for(path: Path | None) -> StateManager:
    root = _resolve_project_root(path)
    return StateManager.for_project(root)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"Forge OS {__version__}")
        raise typer.Exit()


# ─── App Entry Point ──────────────────────────────────────────────────────────

@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show Forge OS version and exit.",
            callback=_version_callback,
        ),
    ] = False,
) -> None:
    """Forge OS local-first lifecycle CLI."""


# ─── Init ─────────────────────────────────────────────────────────────────────

@app.command()
def init(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory to initialize as a Forge project."),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Project name. Defaults to the directory name."),
    ] = None,
    profile: Annotated[
        str,
        typer.Option("--profile", help="Initial profile: minimal, standard, or expert."),
    ] = "minimal",
    adapter: Annotated[
        str,
        typer.Option(
            "--adapter",
            help="Default kernel adapter to enable (e.g. claude-code). Defaults to dummy.",
        ),
    ] = "dummy",
    permission_mode: Annotated[
        str | None,
        typer.Option(
            "--permission-mode",
            help="Claude Code permission mode (claude-code adapter only).",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite scaffold files if they already exist."),
    ] = False,
    interactive: Annotated[
        bool,
        typer.Option("--interactive", help="Prompt for missing init values."),
    ] = False,
) -> None:
    """Initialize a local Forge project."""

    root = (path or Path.cwd()).resolve()
    project_name = name or root.name

    if interactive:
        project_name = typer.prompt("Project name", default=project_name)
        profile = typer.prompt("Profile", default=profile)

    if profile not in SUPPORTED_PROFILES:
        choices = ", ".join(sorted(SUPPORTED_PROFILES))
        console.print(
            f"[red]Unsupported profile `{profile}`.[/red] Choose one of: {choices}."
        )
        raise typer.Exit(code=2)

    # CLI accepts kebab-case (claude-code); config/registry use snake_case.
    adapter_id = adapter.replace("-", "_")
    if adapter_id not in ADAPTER_PRIORITY:
        choices = ", ".join(aid.replace("_", "-") for aid in ADAPTER_PRIORITY)
        console.print(f"[red]Unknown adapter `{adapter}`.[/red] Choose one of: {choices}.")
        raise typer.Exit(code=2)

    if permission_mode is not None and adapter_id != "claude_code":
        console.print("[red]--permission-mode is only valid with --adapter claude-code.[/red]")
        raise typer.Exit(code=2)
    try:
        validate_permission_mode(permission_mode)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    adapter_options: dict[str, object] = {}
    if adapter_id == "claude_code":
        # P055.15: verify the binary works before writing it into the config.
        try:
            version = get_claude_version()
        except ClaudeCodeSpawnError as exc:
            console.print(f"[red]claude-code adapter unavailable:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        console.print(f"Verified claude binary: [cyan]{version}[/cyan]")
        if permission_mode is not None:
            adapter_options["permission_mode"] = permission_mode

    try:
        initialize_project(
            root,
            project_name=project_name,
            profile=profile,
            default_adapter=adapter_id,
            adapter_options=adapter_options or None,
            overwrite=force,
        )
    except ProjectAlreadyInitializedError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except ValidationError as exc:
        console.print(f"[red]Generated configuration failed validation:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Initialized Forge project[/green] at {root}")
    if adapter_id != "dummy":
        console.print(f"Default adapter: [cyan]{adapter_id}[/cyan]")
    console.print("Next: run `forge status` from the project directory.")


# ─── Status ──────────────────────────────────────────────────────────────────

@app.command()
def status(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Show read-only Forge project status."""

    try:
        root, config, state = _resolve_project_status(path)
    except (ProjectNotFoundError, ConfigError, StateError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="Forge Project Status")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Root", str(root))
    table.add_row("Project", config.project.name)
    table.add_row("Profile", config.profile)
    table.add_row("State schema", state.schema_version)
    table.add_row("Current stage", state.current_stage_id or "none")
    table.add_row("Default adapter", config.default_adapter)
    table.add_row("Stale artifacts", str(stale_artifact_count(root)))
    table.add_row("Next action", next_action_for(state))
    console.print(table)

    # P10.11 / FR-BD-002: daemon alerts surface in `forge status`.
    alerts = daemon_alerts()
    if alerts:
        alert_table = Table(title="Daemon Alerts (most recent)")
        alert_table.add_column("Severity", style="bold")
        alert_table.add_column("Source")
        alert_table.add_column("Message")
        alert_table.add_column("At")
        for alert in alerts:
            alert_table.add_row(
                str(alert.get("severity", "")),
                str(alert.get("source", "")),
                str(alert.get("message", "")),
                str(alert.get("created_at", "")),
            )
        console.print(alert_table)


@app.command()
def explain(topic: str = typer.Argument(..., help="Topic to explain.")) -> None:
    """Explain a built-in Forge OS concept."""

    normalized = topic.strip().lower()
    explanation = EXPLAIN_TOPICS.get(normalized)
    if explanation is None:
        console.print(f"[red]Unknown topic `{topic}`.[/red]")
        console.print("Available topics: " + ", ".join(sorted(EXPLAIN_TOPICS)))
        raise typer.Exit(code=1)
    console.print(explanation)


# ─── Stage Commands ───────────────────────────────────────────────────────────

@stage_app.command("list")
def stage_list(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """List pipeline stages in deterministic order."""

    try:
        manager = _state_manager_for(path)
        state = manager.load()
    except (ProjectNotFoundError, StateError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="Forge Stages")
    table.add_column("Stage")
    table.add_column("Status")
    table.add_column("Entered")
    table.add_column("Completed")
    for stage in state.stages:
        marker = "*" if stage.stage_id == state.current_stage_id else ""
        table.add_row(
            f"{stage.stage_id}{marker}",
            stage.status,
            stage.entered_at or "",
            stage.completed_at or "",
        )
    console.print(table)


@stage_app.command("start")
def stage_start(
    stage_id: Annotated[str, typer.Argument(help="Stage id to start.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    spawn_agent: Annotated[
        bool,
        typer.Option("--spawn-agent", help="Spawn the configured stage agent after start."),
    ] = False,
) -> None:
    """Start a stage when deterministic transition rules allow it."""

    try:
        manager = _state_manager_for(path)
        state = manager.start_stage(stage_id)
        record = run_stage_agent(manager.project_root, state, stage_id) if spawn_agent else None
    except (ProjectNotFoundError, StateError, StateTransitionError, AgentExecutionError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Started stage:[/green] {state.current_stage_id}")
    if record is not None:
        console.print(
            f"[green]Spawned agent:[/green] {record.persona_id} "
            f"via {record.adapter} ({record.status})"
        )


@stage_app.command("complete")
def stage_complete(
    stage_id: Annotated[str, typer.Argument(help="Stage id to complete.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Complete an active stage."""

    try:
        manager = _state_manager_for(path)
        manager.complete_stage(stage_id)
    except (ProjectNotFoundError, StateError, StateTransitionError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Completed stage:[/green] {stage_id}")


@stage_app.command("advance")
def stage_advance(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Complete the active stage and start the next stage when available."""

    try:
        manager = _state_manager_for(path)
        state = manager.advance()
    except (ProjectNotFoundError, StateError, StateTransitionError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if state.current_stage_id is None:
        console.print("[green]Pipeline complete.[/green]")
    else:
        console.print(f"[green]Advanced to stage:[/green] {state.current_stage_id}")


@stage_app.command("override")
def stage_override(
    stage_id: Annotated[str, typer.Argument(help="Stage id to force active.")],
    reason: Annotated[str, typer.Option("--reason", "-r", help="Required audit reason.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Force the active stage with an audited reason."""

    try:
        manager = _state_manager_for(path)
        state = manager.override_stage(stage_id, reason=reason)
    except (ProjectNotFoundError, StateError, StateTransitionError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[yellow]Override active stage:[/yellow] {state.current_stage_id}")


# ─── Gate Commands ────────────────────────────────────────────────────────────

@gate_app.command("list")
def gate_list(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """List configured gates."""

    try:
        root = _resolve_project_root(path)
        gates = GateCoordinator(root).load_gates()
    except (ProjectNotFoundError, GateLoadError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="Forge Gates")
    table.add_column("ID")
    table.add_column("Stage")
    table.add_column("Type")
    table.add_column("Severity")
    table.add_column("Enabled")
    for gate in gates:
        table.add_row(gate.id, gate.stage_id or "", gate.type, gate.severity, str(gate.enabled))
    console.print(table)


@gate_app.command("check")
def gate_check(
    stage_id: Annotated[str, typer.Argument(help="Stage id to evaluate gates for.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Evaluate gates for one stage."""

    try:
        root = _resolve_project_root(path)
        manager = StateManager.for_project(root)
        state = manager.load()
        coordinator = GateCoordinator(root, manager.event_bus)
        results = coordinator.evaluate_stage(stage_id)
        state.gates[stage_id] = {
            "blocked": coordinator.has_blocking_failures(results),
            "results": [r.model_dump() for r in results],
        }
        manager.save(state)
    except (ProjectNotFoundError, StateError, GateLoadError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title=f"Gate Check: {stage_id}")
    table.add_column("Gate")
    table.add_column("Status")
    table.add_column("Blocking")
    table.add_column("Summary")
    for result in results:
        table.add_row(result.gate_id, result.status, str(result.blocking), result.summary)
    console.print(table)
    if coordinator.has_blocking_failures(results):
        raise typer.Exit(code=1)


@gate_app.command("report")
def gate_report(
    stage_id: Annotated[
        str | None,
        typer.Option("--stage", help="Stage id to report. Defaults to current stage."),
    ] = None,
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Render a readable gate report."""

    try:
        root = _resolve_project_root(path)
        manager = StateManager.for_project(root)
        state = manager.load()
        target_stage = stage_id or state.current_stage_id
        if target_stage is None:
            console.print("[red]No stage selected and no current stage is active.[/red]")
            raise typer.Exit(code=1)
        coordinator = GateCoordinator(root, manager.event_bus)
        results = coordinator.evaluate_stage(target_stage)
    except (ProjectNotFoundError, StateError, GateLoadError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(coordinator.render_report(results))


# ─── Adapter Commands ─────────────────────────────────────────────────────────

@adapter_app.command("list")
def adapter_list(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """List adapter priority and project configuration status."""

    try:
        root = _resolve_project_root(path)
        config = load_config(root / ".forge" / "config.yaml")
    except (ProjectNotFoundError, ConfigError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="Forge Kernel Adapters")
    table.add_column("Priority")
    table.add_column("ID")
    table.add_column("Implementation")
    table.add_column("Enabled")
    table.add_column("Default")
    for index, adapter_id in enumerate(ADAPTER_PRIORITY, start=1):
        adapter_config = config.adapters.get(adapter_id, {})
        table.add_row(
            str(index),
            adapter_id,
            ADAPTER_CLASS_NAMES[adapter_id],
            str(adapter_config.get("enabled", False)),
            "yes" if adapter_id == config.default_adapter else "",
        )
    console.print(table)


@adapter_app.command("status")
def adapter_status(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Show which adapters are configured and actually selectable right now."""

    try:
        root = _resolve_project_root(path)
        statuses = AdapterUseCases(root).status()
    except (ProjectNotFoundError, ConfigError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="Forge Adapter Status")
    table.add_column("ID")
    table.add_column("Implementation")
    table.add_column("Enabled")
    table.add_column("Default")
    table.add_column("Available")
    table.add_column("Capabilities / Reason")
    for status in statuses:
        if status.available:
            availability = "[green]yes[/green]"
            detail = ", ".join(status.capabilities)
        else:
            availability = "[red]no[/red]"
            detail = f"[dim]{status.reason}[/dim]"
        table.add_row(
            status.adapter_id,
            status.implementation,
            "yes" if status.enabled else "",
            "yes" if status.is_default else "",
            availability,
            detail,
        )
    console.print(table)


@adapter_app.command("enable")
def adapter_enable(
    adapter_id: Annotated[
        str, typer.Argument(help="Adapter id to enable (see `forge adapter list`).")
    ],
    make_default: Annotated[
        bool,
        typer.Option("--default", "-d", help="Also make this adapter the default kernel."),
    ] = False,
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Enable a kernel adapter in this project's config (FR-KA-003)."""

    _apply_adapter_enabled(adapter_id, enabled=True, make_default=make_default, path=path)


@adapter_app.command("disable")
def adapter_disable(
    adapter_id: Annotated[str, typer.Argument(help="Adapter id to disable.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Disable a kernel adapter in this project's config."""

    _apply_adapter_enabled(adapter_id, enabled=False, make_default=False, path=path)


def _apply_adapter_enabled(
    adapter_id: str, *, enabled: bool, make_default: bool, path: Path | None
) -> None:
    # CLI accepts kebab-case (matching `forge init --adapter`); config/registry use snake_case.
    adapter_id = adapter_id.replace("-", "_")
    try:
        root = _resolve_project_root(path)
        result = AdapterUseCases(root).set_enabled(
            adapter_id, enabled=enabled, make_default=make_default
        )
    except (ProjectNotFoundError, ConfigError, AdapterRegistryError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    verb = "enabled" if result.enabled else "disabled"
    state = "now" if result.changed else "already"
    default_note = " [cyan](default kernel)[/cyan]" if result.is_default else ""
    console.print(f"[green]Adapter `{result.adapter_id}` {state} {verb}.[/green]{default_note}")
    if result.enabled and not result.available:
        console.print(f"[yellow]⚠ Not available yet:[/yellow] {result.reason}")


# ─── Agent Commands ───────────────────────────────────────────────────────────

@agent_app.command("list")
def agent_list(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """List built-in and project-local personas."""

    try:
        root = _resolve_project_root(path)
        personas = load_personas(root)
    except (ProjectNotFoundError, AgentLoadError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="Forge Agent Personas")
    table.add_column("ID", no_wrap=True)
    table.add_column("Name")
    table.add_column("Category")
    table.add_column("Stages")
    table.add_column("Contract")
    for persona in sorted(personas.values(), key=lambda p: p.id):
        table.add_row(
            persona.id, persona.name, persona.category,
            ",".join(persona.stage_ids), persona.output_contract_id or "",
        )
    console.print(table)


@agent_app.command("contracts")
def agent_contracts(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """List output contracts."""

    try:
        root = _resolve_project_root(path)
        contracts = load_contracts(root)
    except (ProjectNotFoundError, AgentLoadError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="Forge Output Contracts")
    table.add_column("ID")
    table.add_column("Stage")
    table.add_column("Persona")
    table.add_column("Requirements")
    for contract in sorted(contracts.values(), key=lambda c: c.id):
        table.add_row(
            contract.id, contract.stage_id, contract.persona_id,
            str(len(contract.required_outputs)),
        )
    console.print(table)


@agent_app.command("run")
def agent_run(
    stage_id: Annotated[
        str | None,
        typer.Option("--stage", help="Stage id to run. Defaults to current active stage."),
    ] = None,
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Run the configured stage agent through the selected kernel adapter."""

    try:
        manager = _state_manager_for(path)
        state = manager.load()
        target_stage = stage_id or state.current_stage_id
        if target_stage is None:
            console.print("[red]No stage selected and no current stage is active.[/red]")
            raise typer.Exit(code=1)
        record = run_stage_agent(manager.project_root, state, target_stage)
    except (ProjectNotFoundError, StateError, AgentExecutionError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[green]Agent completed:[/green] {record.persona_id} "
        f"via {record.adapter} ({record.status})"
    )


# ─── Lesson Commands ───────────────────────────────────────────────────────────

@lesson_app.command("list")
def lesson_list(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option("--status", help="Filter by pending, approved, or deprecated."),
    ] = None,
    stage_id: Annotated[
        str | None,
        typer.Option("--stage", help="Filter by applicable stage id."),
    ] = None,
    tag: Annotated[str | None, typer.Option("--tag", help="Filter by tag.")] = None,
) -> None:
    """List project lessons."""

    try:
        root = _resolve_project_root(path)
        lessons = LessonStore(root).list(status=status, stage_id=stage_id, tag=tag)
    except (ProjectNotFoundError, LessonStoreError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="Forge Lessons")
    table.add_column("ID", max_width=16)
    table.add_column("Status", no_wrap=True)
    table.add_column("Confidence", no_wrap=True)
    table.add_column("Stage", no_wrap=True)
    table.add_column("Tags")
    table.add_column("Text")
    for lesson in lessons:
        table.add_row(
            lesson.id, lesson.status, f"{lesson.confidence:.2f}",
            lesson.stage_id or "global", ",".join(lesson.tags), lesson.text,
        )
    console.print(table)


@lesson_app.command("add")
def lesson_add(
    text: Annotated[str, typer.Argument(help="Lesson text to store.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    confidence: Annotated[
        float,
        typer.Option("--confidence", min=0.0, max=1.0, help="Confidence from 0.0 to 1.0."),
    ] = 0.5,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Applicability tag. Can be repeated."),
    ] = None,
    stage_id: Annotated[
        str | None,
        typer.Option("--stage", help="Stage id this lesson applies to."),
    ] = None,
    approve: Annotated[
        bool,
        typer.Option("--approve", help="Immediately approve this manual lesson."),
    ] = False,
) -> None:
    """Add a manual project lesson."""

    try:
        root = _resolve_project_root(path)
        store = LessonStore(root)
        lesson = store.add(
            text,
            confidence=confidence,
            tags=tag or [],
            stage_id=stage_id,
            source="manual",
            status="approved" if approve else "pending",
        )
        if approve:
            lesson = store.approve(lesson.id)
    except (ProjectNotFoundError, LessonStoreError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Added lesson:[/green] {lesson.id} ({lesson.status})")


@lesson_app.command("approve")
def lesson_approve(
    lesson_id: Annotated[str, typer.Argument(help="Lesson id to approve.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Approve a pending lesson so it can enter future context."""

    try:
        root = _resolve_project_root(path)
        lesson = LessonStore(root).approve(lesson_id)
    except (ProjectNotFoundError, LessonStoreError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Approved lesson:[/green] {lesson.id}")


@lesson_app.command("deprecate")
def lesson_deprecate(
    lesson_id: Annotated[str, typer.Argument(help="Lesson id to deprecate.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Deprecate a lesson so it is excluded from future context."""

    try:
        root = _resolve_project_root(path)
        lesson = LessonStore(root).deprecate(lesson_id)
    except (ProjectNotFoundError, LessonStoreError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[yellow]Deprecated lesson:[/yellow] {lesson.id}")


# ─── Reflection Commands ─────────────────────────────────────────────────────

@reflection_app.command("list")
def reflection_list(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    stage_id: Annotated[str | None, typer.Option("--stage", help="Filter by stage id.")] = None,
) -> None:
    """List stored reflections."""

    try:
        root = _resolve_project_root(path)
        reflections = ReflectionStore(root).list(stage_id=stage_id)
    except (ProjectNotFoundError, ReflectionStoreError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="Forge Reflections")
    table.add_column("ID", max_width=16)
    table.add_column("Stage", no_wrap=True)
    table.add_column("Event", no_wrap=True)
    table.add_column("Created")
    table.add_column("Summary")
    for reflection in reflections:
        table.add_row(
            reflection.id, reflection.stage_id or "", reflection.event_type,
            reflection.created_at, reflection.summary,
        )
    console.print(table)


@reflection_app.command("show")
def reflection_show(
    reflection_id: Annotated[str, typer.Argument(help="Reflection id to show.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Show one reflection as YAML."""

    try:
        root = _resolve_project_root(path)
        reflection = ReflectionStore(root).get(reflection_id)
    except (ProjectNotFoundError, ReflectionStoreError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(yaml.safe_dump(reflection.model_dump(mode="json"), sort_keys=False))


# ─── Artifact Commands ────────────────────────────────────────────────────────

@artifact_app.command("list")
def artifact_list(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    status: Annotated[str | None, typer.Option("--status", help="Filter by status.")] = None,
    stage_id: Annotated[str | None, typer.Option("--stage", help="Filter by stage.")] = None,
) -> None:
    """List registered artifacts."""

    try:
        root = _resolve_project_root(path)
        artifacts = ArtifactRegistry(root).list(status=status, stage_id=stage_id)
    except (ProjectNotFoundError, ArtifactRegistryError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="Forge Artifacts")
    table.add_column("Path")
    table.add_column("Stage", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Tokens", no_wrap=True)
    table.add_column("Dependencies")
    for artifact in artifacts:
        table.add_row(
            artifact.path, artifact.stage_id or "", artifact.status,
            str(artifact.token_estimate), ",".join(artifact.dependencies),
        )
    console.print(table)


@artifact_app.command("register")
def artifact_register(
    artifact_path: Annotated[str, typer.Argument(help="Project-relative artifact path.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    stage_id: Annotated[str | None, typer.Option("--stage", help="Owning stage id.")] = None,
    dependency: Annotated[
        list[str] | None,
        typer.Option("--dependency", help="Dependency path. Can be repeated."),
    ] = None,
) -> None:
    """Register or update one artifact."""

    try:
        root = _resolve_project_root(path)
        artifact = ArtifactRegistry(root).register(
            artifact_path, stage_id=stage_id,
            dependencies=dependency or [], metadata={"registered_by": "cli"},
        )
    except (ProjectNotFoundError, ArtifactRegistryError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Registered artifact:[/green] {artifact.path} ({artifact.status})")


@artifact_app.command("refresh")
def artifact_refresh(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Refresh artifact hashes and mark stale downstream artifacts."""

    try:
        root = _resolve_project_root(path)
        document = ArtifactRegistry(root).refresh()
    except (ProjectNotFoundError, ArtifactRegistryError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    stale = len([a for a in document.artifacts if a.status == "stale"])
    console.print(f"[green]Refreshed artifacts:[/green] {len(document.artifacts)} ({stale} stale)")


# ─── Context Commands ──────────────────────────────────────────────────────────

@context_app.command("select")
def context_select(
    stage_id: Annotated[str, typer.Argument(help="Stage id to select context for.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    token_budget: Annotated[
        int,
        typer.Option("--token-budget", min=1, help="Maximum estimated tokens."),
    ] = 2000,
) -> None:
    """Select deterministic pruned context for one stage."""

    try:
        root = _resolve_project_root(path)
        selection = ContextPruner(root).select(stage_id, token_budget=token_budget)
    except (ProjectNotFoundError, ContextPrunerError, ArtifactRegistryError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title=f"Context Selection: {stage_id}")
    table.add_column("Path")
    table.add_column("Priority", no_wrap=True)
    table.add_column("Tokens", no_wrap=True)
    table.add_column("Reason")
    for item in selection.selected:
        table.add_row(item.path, str(item.priority), str(item.token_estimate), item.reason)
    console.print(table)
    console.print(
        f"Selected {len(selection.selected)} artifact(s), "
        f"{selection.total_tokens}/{selection.token_budget} estimated tokens."
    )


# ─── Event Commands ───────────────────────────────────────────────────────────

@events_app.command("list")
def events_list(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    event_type: Annotated[str | None, typer.Option("--type", help="Filter by event type.")] = None,
    stage_id: Annotated[str | None, typer.Option("--stage", help="Filter by stage id.")] = None,
) -> None:
    """List normalized lifecycle events."""

    try:
        root = _resolve_project_root(path)
        events = filter_events(
            read_events(root / ".forge" / "events.jsonl"),
            event_type=event_type, stage_id=stage_id,
        )
    except (ProjectNotFoundError, EventLogError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="Forge Events")
    table.add_column("Timestamp")
    table.add_column("Type")
    table.add_column("Stage")
    table.add_column("Event ID")
    for event in events:
        table.add_row(event.timestamp, event.event_type, event.stage_id or "", event.event_id)
    console.print(table)


@events_app.command("tail")
def events_tail(
    count: Annotated[
        int,
        typer.Option("--count", "-n", min=1, help="Number of events to show."),
    ] = 10,
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Show the last N normalized lifecycle events."""

    try:
        root = _resolve_project_root(path)
        events = read_events(root / ".forge" / "events.jsonl")[-count:]
    except (ProjectNotFoundError, EventLogError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    for event in events:
        console.print(
            f"{event.timestamp} {event.event_type} "
            f"stage={event.stage_id or '-'} id={event.event_id}"
        )


# ─── Config Commands ──────────────────────────────────────────────────────────

@config_app.command("show")
def config_show(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Print the validated Forge configuration as YAML."""

    try:
        root, config, _state = _resolve_project_status(path)
    except (ProjectNotFoundError, ConfigError, StateError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"# {root / '.forge' / 'config.yaml'}")
    console.print(yaml.safe_dump(config.model_dump(), sort_keys=False, allow_unicode=True))


@config_app.command("validate")
def config_validate(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project or config file path."),
    ] = None,
) -> None:
    """Validate Forge configuration."""

    try:
        if path and path.resolve().is_file():
            _ = load_config(path.resolve())
        else:
            root, _config, _state = _resolve_project_status(path)
            config_path = root / ".forge" / "config.yaml"
    except (ProjectNotFoundError, ConfigError, StateError) as exc:
        console.print(f"[red]Invalid Forge config:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Valid Forge config:[/green] {config_path}")


if __name__ == "__main__":
    app()