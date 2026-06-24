"""Tests for the `forge cost` CLI sub-app (FR-TE-001/004, FR-COST-002)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from forge_os.cli.commands.cost import cost_app
from forge_os.events.store import EventStore
from forge_os.project.scaffold import initialize_project

runner = CliRunner()


def _append_spawn(
    root: Path, run_id: str, stage: str, cost: float | None, adapter: str = "claude_code"
) -> None:
    store = EventStore(root / ".forge" / "events.db")
    store.append(run_id, "AdapterSpawnStarted", {"adapter": adapter, "stage_id": stage})
    store.append(
        run_id,
        "AdapterSpawnCompleted",
        {
            "adapter": adapter,
            "metadata": {
                "usage": {"input_tokens": 120, "output_tokens": 60},
                "total_cost_usd": cost,
            },
        },
    )
    store.close()


def _seeded(tmp_path: Path, stage: str = "build") -> Path:
    initialize_project(tmp_path, project_name="Cost", profile="minimal")
    _append_spawn(tmp_path, "r1", stage, 0.0123)
    return tmp_path


def test_renders_table_for_recorded_spend(tmp_path: Path) -> None:
    result = runner.invoke(cost_app, ["--path", str(_seeded(tmp_path))])
    assert result.exit_code == 0
    assert "Forge Cost" in result.output
    assert "build" in result.output
    assert "$0.0123" in result.output
    assert "source adapters" in result.output  # footer renders the data source
    assert "claude_code" in result.output


def test_empty_project_reports_no_data(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Empty", profile="minimal")
    result = runner.invoke(cost_app, ["--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "No recorded spawn cost events" in result.output


def test_json_output(tmp_path: Path) -> None:
    result = runner.invoke(cost_app, ["--path", str(_seeded(tmp_path)), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["production_spawns"] == 1
    assert payload["stages"][0]["stage_id"] == "build"
    assert "evolution_note" in payload


def test_stage_filter(tmp_path: Path) -> None:
    root = _seeded(tmp_path, stage="build")
    _append_spawn(root, "r2", "srs", 0.0001)
    result = runner.invoke(cost_app, ["--path", str(root), "--stage", "srs", "--json"])
    payload = json.loads(result.output)
    assert [s["stage_id"] for s in payload["stages"]] == ["srs"]


def test_no_pricing_shown_when_cost_absent(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="NP", profile="minimal")
    _append_spawn(tmp_path, "r1", "build", None, adapter="dummy")
    result = runner.invoke(cost_app, ["--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "no pricing" in result.output


def test_stage_filter_markup_escaped(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Esc", profile="minimal")
    result = runner.invoke(cost_app, ["--path", str(tmp_path), "--stage", "[red]x[/red]"])
    assert result.exit_code == 0
    assert "[red]x[/red]" in result.output  # rendered literally, not consumed as markup


def test_missing_project_errors(tmp_path: Path) -> None:
    empty = tmp_path / "x"
    empty.mkdir()
    result = runner.invoke(cost_app, ["--path", str(empty)])
    assert result.exit_code == 1


def test_registered_on_top_level_app(tmp_path: Path) -> None:
    from forge_os.cli.main import app

    result = runner.invoke(app, ["cost", "--path", str(_seeded(tmp_path))])
    assert result.exit_code == 0
    assert "Forge Cost" in result.output
