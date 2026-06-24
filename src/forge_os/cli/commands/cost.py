"""`forge cost` — report recorded agent token + $ spend (FR-TE-001/004, FR-COST-002).

Read-only aggregation of recorded `AdapterSpawnCompleted` events, grouped by
stage. Production data comes from adapters that record cost (today: claude_code);
shadow/canary and Dreamer/Skill-Miner streams have no data source yet and are
reported as such, never fabricated.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape
from rich.table import Table

from forge_os.cli.commands._shared import console, resolve_project_root
from forge_os.project.detect import ProjectNotFoundError
from forge_os.schemas.cost import CostReport

cost_app = typer.Typer(help="Report recorded agent token + $ spend.")


@cost_app.callback(invoke_without_command=True)
def cost(
    ctx: typer.Context,
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    stage: Annotated[
        str | None,
        typer.Option("--stage", "-s", help="Limit to a single stage id."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit the report as JSON."),
    ] = False,
) -> None:
    """Show token + $ spend by stage from recorded production spawns."""

    if ctx.invoked_subcommand is not None:
        return

    from forge_os.use_cases.cost import CostUseCases

    try:
        root = resolve_project_root(path)
    except ProjectNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    report = CostUseCases(root).report(stage_filter=stage)

    if json_output:
        typer.echo(json.dumps(report.model_dump(), indent=2))
    else:
        _render(report, stage)


def _cost_cell(value: float | None) -> str:
    # No pricing (e.g. an adapter without a price model) is shown as such, not as 0.
    return f"${value:.4f}" if value is not None else "no pricing"


def _render(report: CostReport, stage_filter: str | None) -> None:
    console.print("[bold]Forge Cost — production spend[/bold]")

    if not report.stages:
        scope = f" for stage '{escape(stage_filter)}'" if stage_filter else ""
        console.print(f"[dim]No recorded spawn cost events{scope} yet.[/dim]")
    else:
        table = Table()
        table.add_column("Stage")
        table.add_column("Spawns", justify="right")
        table.add_column("Input", justify="right")
        table.add_column("Output", justify="right")
        table.add_column("Total tok", justify="right")
        table.add_column("Cost (USD)", justify="right")
        for stage in report.stages:
            table.add_row(
                escape(stage.stage_id),
                str(stage.spawns),
                str(stage.input_tokens),
                str(stage.output_tokens),
                str(stage.total_tokens),
                _cost_cell(stage.cost_usd),
            )
        table.add_row(
            "[bold]total[/bold]",
            str(report.production_spawns),
            str(report.total_input_tokens),
            str(report.total_output_tokens),
            str(report.total_tokens),
            _cost_cell(report.total_cost_usd),
        )
        console.print(table)
        if report.adapters:
            console.print(f"[dim]source adapters: {escape(', '.join(report.adapters))}[/dim]")

    console.print(f"[dim]evolution: {report.evolution_note}[/dim]")
    console.print(f"[dim]exploration: {report.exploration_note}[/dim]")
