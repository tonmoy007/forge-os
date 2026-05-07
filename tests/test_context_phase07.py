from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from forge_os.agents.executor import run_stage_agent
from forge_os.cli.main import app
from forge_os.context.pruner import ContextPruner
from forge_os.context.registry import ArtifactRegistry
from forge_os.project.scaffold import initialize_project
from forge_os.project.status import load_state

runner = CliRunner()


def test_artifact_registry_persists_adg_edges(tmp_path: Path) -> None:
    _ = initialize_project(tmp_path, project_name="Demo", profile="minimal")
    _ = (tmp_path / "SRS.md").write_text("# Requirements\n", encoding="utf-8")
    output = tmp_path / "pipeline" / "log" / "build-agent-output.md"
    _ = output.write_text("# Build\n", encoding="utf-8")

    registry = ArtifactRegistry(tmp_path)
    srs = registry.register("SRS.md", stage_id="srs")
    build = registry.register(
        "pipeline/log/build-agent-output.md",
        stage_id="build",
        dependencies=["SRS.md"],
    )

    document = registry.load()
    graph = json.loads((tmp_path / ".forge" / "adg.json").read_text(encoding="utf-8"))

    assert len(document.artifacts) == 2
    assert srs.path == "SRS.md"
    assert build.dependencies == ["SRS.md"]
    assert {edge["source"] + "->" + edge["target"] for edge in graph["edges"]} == {
        "SRS.md->pipeline/log/build-agent-output.md"
    }


def test_refresh_marks_downstream_artifacts_stale(tmp_path: Path) -> None:
    _ = initialize_project(tmp_path, project_name="Demo", profile="minimal")
    _ = (tmp_path / "SRS.md").write_text("# Requirements\n", encoding="utf-8")
    build_path = tmp_path / "pipeline" / "log" / "build-agent-output.md"
    _ = build_path.write_text("# Build\n", encoding="utf-8")
    registry = ArtifactRegistry(tmp_path)
    _ = registry.register("SRS.md", stage_id="srs")
    _ = registry.register(
        "pipeline/log/build-agent-output.md",
        stage_id="build",
        dependencies=["SRS.md"],
    )

    _ = (tmp_path / "SRS.md").write_text("# Requirements changed\n", encoding="utf-8")
    refreshed = registry.refresh()
    by_path = {artifact.path: artifact for artifact in refreshed.artifacts}

    assert by_path["SRS.md"].status == "fresh"
    assert by_path["pipeline/log/build-agent-output.md"].status == "stale"


def test_context_pruner_enforces_budget_and_logs_selection(tmp_path: Path) -> None:
    _ = initialize_project(tmp_path, project_name="Demo", profile="minimal")
    _ = (tmp_path / "SRS.md").write_text("A" * 120, encoding="utf-8")
    build_path = tmp_path / "pipeline" / "log" / "build-agent-output.md"
    _ = build_path.write_text("short", encoding="utf-8")
    registry = ArtifactRegistry(tmp_path)
    _ = registry.register("SRS.md", stage_id="srs")
    _ = registry.register(
        "pipeline/log/build-agent-output.md",
        stage_id="build",
        dependencies=["SRS.md"],
    )

    selection = ContextPruner(tmp_path).select("build", token_budget=10)

    assert selection.total_tokens <= 10
    assert [item.path for item in selection.selected] == ["pipeline/log/build-agent-output.md"]
    assert selection.omitted[0]["path"] == "SRS.md"
    audit_lines = (tmp_path / ".forge" / "context-selections.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    assert len(audit_lines) == 1
    assert json.loads(audit_lines[0])["selection_id"] == selection.selection_id


def test_agent_run_registers_stage_outputs_and_context_metadata(tmp_path: Path) -> None:
    _ = initialize_project(tmp_path, project_name="Demo", profile="minimal")
    state = load_state(tmp_path)

    record = run_stage_agent(tmp_path, state, "srs")

    registry = ArtifactRegistry(tmp_path)
    artifacts = registry.list(stage_id="srs")
    assert record.metadata["context_selection_id"]
    assert artifacts[0].path == "SRS.md"
    assert artifacts[0].status == "fresh"


def test_artifact_and_context_cli_commands() -> None:
    with runner.isolated_filesystem():
        init_result = runner.invoke(app, ["init", "--name", "Demo"])
        _ = Path("SRS.md").write_text("# Requirements\n", encoding="utf-8")
        register_result = runner.invoke(
            app,
            ["artifact", "register", "SRS.md", "--stage", "srs"],
        )
        list_result = runner.invoke(app, ["artifact", "list"])
        select_result = runner.invoke(app, ["context", "select", "srs", "--token-budget", "50"])

        assert init_result.exit_code == 0, init_result.output
        assert register_result.exit_code == 0, register_result.output
        assert list_result.exit_code == 0, list_result.output
        assert "SRS.md" in list_result.output
        assert select_result.exit_code == 0, select_result.output
        assert "Selected 1 artifact" in select_result.output


def test_status_displays_stale_artifact_count() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        _ = Path("SRS.md").write_text("# Requirements\n", encoding="utf-8")
        build_path = Path("pipeline/log/build-agent-output.md")
        _ = build_path.write_text("# Build\n", encoding="utf-8")
        runner.invoke(app, ["artifact", "register", "SRS.md", "--stage", "srs"])
        runner.invoke(
            app,
            [
                "artifact",
                "register",
                "pipeline/log/build-agent-output.md",
                "--stage",
                "build",
                "--dependency",
                "SRS.md",
            ],
        )
        _ = Path("SRS.md").write_text("# Requirements changed\n", encoding="utf-8")
        refresh_result = runner.invoke(app, ["artifact", "refresh"])
        status_result = runner.invoke(app, ["status"])

        assert refresh_result.exit_code == 0, refresh_result.output
        assert "1 stale" in refresh_result.output
        assert status_result.exit_code == 0, status_result.output
        assert "Stale artifacts" in status_result.output
