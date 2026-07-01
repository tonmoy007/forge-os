"""`forge trace` — render a correlated trace of neutral spans (FR-SEM-002, FR-OBS-001).

Read-only view over the dual-stream tracer's live projection. Bare `forge trace`
lists the available traces; `forge trace <trace_id>` shows one trace's spans.
Registered as a top-level command (not a sub-app) because a positional argument on
an `add_typer` group is parsed as a subcommand name — `forge trace <id> --json`
would break.
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
from forge_os.schemas.observability import TraceDetail, TraceListReport

_STATUS_STYLE = {"error": "red", "ok": "green", "unset": "dim"}


def _status_cell(status: str) -> str:
    return f"[{_STATUS_STYLE.get(status, 'dim')}]{escape(status)}[/]"


def trace_command(
    trace_id: Annotated[
        str | None,
        typer.Argument(help="Trace id to show. Omit to list all traces."),
    ] = None,
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit the trace(s) as JSON."),
    ] = False,
) -> None:
    """Show a correlated trace of reasoning + audit spans."""

    from forge_os.use_cases.observability import ObservabilityUseCases

    try:
        root = resolve_project_root(path)
    except ProjectNotFoundError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(code=1) from exc

    use_cases = ObservabilityUseCases(root)

    if trace_id is None:
        report = use_cases.list_traces()
        if json_output:
            typer.echo(json.dumps(report.model_dump(), indent=2))
        else:
            _render_list(report)
        return

    detail = use_cases.get_trace(trace_id)
    if json_output:
        typer.echo(json.dumps(detail.model_dump(), indent=2))
    else:
        _render_detail(detail)


def _render_list(report: TraceListReport) -> None:
    console.print("[bold]Forge Trace — available traces[/bold]")
    if not report.traces:
        console.print("[dim]No traces recorded yet.[/dim]")
        return
    table = Table()
    table.add_column("Trace ID")
    table.add_column("Root span")
    table.add_column("Kinds")
    table.add_column("Spans", justify="right")
    table.add_column("Status")
    table.add_column("Start")
    for summary in report.traces:
        table.add_row(
            escape(summary.trace_id),
            escape(summary.root_name),
            escape(", ".join(summary.kinds)),
            str(summary.span_count),
            _status_cell(summary.status),
            escape(summary.start_time),
        )
    console.print(table)
    console.print("[dim]Run `forge trace <trace_id>` for a trace's spans.[/dim]")


def _render_detail(detail: TraceDetail) -> None:
    console.print(f"[bold]Forge Trace — {escape(detail.trace_id)}[/bold]")
    if not detail.found:
        console.print(f"[dim]No spans for trace '{escape(detail.trace_id)}'.[/dim]")
        return
    console.print(
        f"[dim]{detail.span_count} span(s) · kinds: {escape(', '.join(detail.kinds))} · "
        f"status: {escape(detail.status)}[/dim]"
    )
    table = Table()
    table.add_column("Span ID")
    table.add_column("Kind")
    table.add_column("Status")
    table.add_column("Name")
    table.add_column("Start")
    for span in detail.spans:
        table.add_row(
            escape(span.span_id),
            escape(span.kind),
            _status_cell(span.status),
            escape(span.name),
            escape(span.start_time),
        )
    console.print(table)
    console.print("[dim]Span attributes are available with `--json`.[/dim]")
