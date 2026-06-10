"""Lazy context budget commands (Phase 10 WS-D, FR-LCB-001..004)."""

from pathlib import Path
from typing import Annotated

import typer

from forge_os.cli.commands._shared import console, resolve_project_root

lazy_app = typer.Typer(help="Inspect lazy context budgets and savings.")


@lazy_app.command("budget")
def lazy_budget(
    stage: Annotated[
        str,
        typer.Option("--stage", "-s", help="Stage ID to build lazy context for."),
    ],
    budget: Annotated[
        int,
        typer.Option("--budget", "-b", help="Total context token budget."),
    ] = 2000,
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Show the lazy context bundle and its token accounting for a stage."""

    try:
        from forge_os.use_cases.lazy_context import LazyContextUseCases

        root = resolve_project_root(path)
        bundle = LazyContextUseCases(root).budget(stage, token_budget=budget)
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print("[bold]Lazy Context Budget[/bold]")
    console.print(f"Stage: {bundle['stage_id']}")
    console.print(f"Lazy tokens: {bundle['lazy_tokens']} (stage budget {bundle['token_budget']})")
    status_icon = "✅" if bundle["within_budget"] else "⚠️"
    console.print(f"{status_icon} within budget: {bundle['within_budget']}")
    console.print(f"Skills on menu: {len(bundle['skills_menu'])}")
    for entry in bundle["skills_menu"]:
        console.print(f"  • {entry['name']}: {entry['description']}")
    console.print(f"Lessons indexed: {len(bundle['lesson_index'])}")
    for entry in bundle["lesson_index"]:
        console.print(f"  • {entry['id']} ({entry['confidence']}): {entry['summary']}")
    if bundle["trimmed"]:
        trimmed = ", ".join(bundle["trimmed"])
        console.print(f"[yellow]Trimmed {len(bundle['trimmed'])} entries: {trimmed}[/yellow]")


@lazy_app.command("lazy-stats")
def lazy_stats(
    stage: Annotated[
        str,
        typer.Option("--stage", "-s", help="Stage ID to compare context costs for."),
    ],
    budget: Annotated[
        int,
        typer.Option("--budget", "-b", help="Total context token budget."),
    ] = 2000,
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Compare eager vs lazy context token costs for a stage."""

    try:
        from forge_os.use_cases.lazy_context import LazyContextUseCases

        root = resolve_project_root(path)
        stats = LazyContextUseCases(root).lazy_stats(stage, token_budget=budget)
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print("[bold]Lazy Context Stats[/bold]")
    console.print(f"Eager tokens: {stats['eager_tokens']}")
    console.print(f"Lazy tokens: {stats['lazy_tokens']}")
    console.print(f"Reduction: {stats['reduction_pct']}%")
    console.print(f"Budget: {stats['budget']} (within budget: {stats['within_budget']})")
