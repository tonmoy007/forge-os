"""Tests for the `forge trace` CLI command (FR-SEM-002, FR-OBS-001 — S3)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from forge_os.cli.main import app
from forge_os.events.store import EventStore
from forge_os.project.scaffold import initialize_project

runner = CliRunner()


def _seed(tmp_path: Path, run_id: str = "run-1") -> Path:
    initialize_project(tmp_path, project_name="Obs", profile="minimal")
    store = EventStore(tmp_path / ".forge" / "events.db")
    store.append(run_id, "AdapterSpawnStarted", {"stage": "srs"})
    store.append(run_id, "AdapterSpawnCompleted", {"metadata": {"total_cost_usd": 0.02}})
    store.close()
    return tmp_path


def test_bare_trace_lists_traces(tmp_path: Path) -> None:
    result = runner.invoke(app, ["trace", "--path", str(_seed(tmp_path))])
    assert result.exit_code == 0, result.output
    assert "available traces" in result.output
    assert "run-1" in result.output


def test_trace_detail_renders_spans(tmp_path: Path) -> None:
    result = runner.invoke(app, ["trace", "run-1", "--path", str(_seed(tmp_path))])
    assert result.exit_code == 0, result.output
    assert "AdapterSpawnStarted" in result.output
    assert "AdapterSpawnCompleted" in result.output


def test_trace_id_then_json_flag_parses(tmp_path: Path) -> None:
    # Positional id FOLLOWED by an option — the exact ordering a Typer sub-app
    # group mis-parses as a subcommand. The top-level command must accept it.
    root = _seed(tmp_path)
    result = runner.invoke(app, ["trace", "run-1", "--path", str(root), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["trace_id"] == "run-1"
    assert payload["found"] is True
    assert payload["status"] == "ok"
    assert [s["name"] for s in payload["spans"]] == [
        "AdapterSpawnStarted",
        "AdapterSpawnCompleted",
    ]
    assert payload["spans"][0]["attributes"] == {"stage": "srs"}


def test_unknown_trace_reports_empty_not_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["trace", "missing", "--path", str(_seed(tmp_path))])
    assert result.exit_code == 0
    assert "No spans for trace 'missing'" in result.output


def test_empty_project_reports_no_traces(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Empty", profile="minimal")
    result = runner.invoke(app, ["trace", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "No traces recorded yet" in result.output


def test_missing_project_errors(tmp_path: Path) -> None:
    empty = tmp_path / "x"
    empty.mkdir()
    result = runner.invoke(app, ["trace", "--path", str(empty)])
    assert result.exit_code == 1


def test_trace_id_markup_escaped(tmp_path: Path) -> None:
    # trace_id (= a run_id from event data) must render literally, not as Rich markup.
    root = _seed(tmp_path, run_id="[red]evil[/red]")
    result = runner.invoke(app, ["trace", "[red]evil[/red]", "--path", str(root)])
    assert result.exit_code == 0
    assert "[red]evil[/red]" in result.output


def test_list_json_output(tmp_path: Path) -> None:
    result = runner.invoke(app, ["trace", "--path", str(_seed(tmp_path)), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["traces"][0]["trace_id"] == "run-1"
    assert payload["traces"][0]["span_count"] == 2
