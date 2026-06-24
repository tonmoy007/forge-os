"""Health subsystem commands."""

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape

from forge_os.cli.commands._shared import console, resolve_project_root, resolve_project_status
from forge_os.project.status import stale_artifact_count

health_app = typer.Typer(help="Check Forge OS subsystem health.")


@health_app.command("check")
def health_check(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Run full system health check across all subsystems."""

    try:
        from forge_os.use_cases.health import HealthUseCases

        root = resolve_project_root(path)
        use_cases = HealthUseCases(root)
        report = use_cases.run_full_check()
    except ImportError:
        console.print(
            "[yellow]Running basic health check "
            "(full health module not available).[/yellow]"
        )
        _run_basic_health_check(path)
        return
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print("[bold]Forge OS Health Report[/bold]")
    for subsystem, result in report.items():
        status_icon = "✅" if result.get("healthy", False) else "❌"
        console.print(f"{status_icon} {subsystem}: {result.get('message', 'unknown')}")


@health_app.command("knowledge")
def health_knowledge(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit the report as JSON."),
    ] = False,
) -> None:
    """Scan knowledge integrity (FR-HD-002) + report the artifact token budget.

    Surfaces ``KnowledgeUseCases``: stale lesson references and duplicate/
    conflicting lessons (the FR-HD-002 integrity scans), plus the project-wide
    artifact token-budget aggregate. Exits non-zero when integrity issues are
    found, so it is scriptable.
    """

    from forge_os.use_cases.knowledge import KnowledgeUseCases

    # The project + its stores raise typed RuntimeError subclasses
    # (ProjectNotFoundError, LessonStoreError, ArtifactRegistryError) on a
    # missing/corrupt `.forge`. cli/ must not import those concrete types (layer
    # rule), so catch the shared RuntimeError base and surface a clean message
    # instead of leaking a raw traceback and internal file paths.
    try:
        use_cases = KnowledgeUseCases(resolve_project_root(path))
        stale_references = use_cases.scan_lesson_references()
        conflicts = use_cases.scan_lesson_conflicts()
        budget = use_cases.report_token_budget()
    except RuntimeError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(code=1) from exc

    issue_count = len(stale_references) + len(conflicts)

    if json_output:
        payload = {
            "integrity": {
                "stale_references": stale_references,
                "conflicts": conflicts,
                "issue_count": issue_count,
            },
            "artifact_budget": budget,
        }
        typer.echo(json.dumps(payload, indent=2))
    else:
        _render_knowledge(stale_references, conflicts, budget, issue_count)

    if issue_count:
        raise typer.Exit(code=1)


def _render_knowledge(
    stale_references: list[dict],
    conflicts: list[dict],
    budget: dict,
    issue_count: int,
) -> None:
    """Render the integrity findings and artifact-budget aggregate."""

    console.print("[bold]Knowledge Integrity[/bold] (FR-HD-002)")
    if issue_count == 0:
        console.print("✅ No integrity issues found")
    else:
        # Lesson text/references are user-controlled — escape so Rich renders
        # any `[...]` literally rather than as markup.
        for ref in stale_references:
            console.print(
                f"⚠️ stale reference: lesson {escape(str(ref['lesson_id']))} → "
                f"{escape(str(ref['reference']))} ({escape(str(ref['issue']))})"
            )
        for conflict in conflicts:
            console.print(
                f"⚠️ duplicate lesson: {escape(str(conflict['duplicate_id']))} "
                f"== {escape(str(conflict['existing_id']))}"
            )

    console.print()
    console.print("[bold]Artifact Token Budget[/bold]")
    console.print(
        f"  artifacts: {budget['total_artifacts']} "
        f"({budget['fresh_count']} fresh, {budget['stale_count']} stale)"
    )
    console.print(
        f"  tokens: {budget['total_tokens']} total, "
        f"{budget['avg_tokens_per_artifact']} avg/artifact "
        f"({budget['fresh_tokens']} fresh, {budget['stale_tokens']} stale)"
    )


def _run_basic_health_check(path: Path | None) -> None:
    """Basic health check when the full health module is unavailable."""
    try:
        root, config, state = resolve_project_status(path)
        console.print(f"✅ Config: loaded (profile={config.profile})")
        console.print(
            f"✅ State: {state.schema_version} "
            f"(current stage={state.current_stage_id or 'none'})"
        )
        stale = stale_artifact_count(root)
        console.print(f"{'✅' if stale == 0 else '⚠️'} Artifacts: {stale} stale")
    except Exception as exc:
        console.print(f"❌ Health check failed: {exc}")