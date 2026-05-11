from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from forge_os.cli.main import app

runner = CliRunner()


EXPECTED_INIT_PATHS = [
    ".forge/config.yaml",
    ".forge/state.json",
    ".forge/events.jsonl",
    ".forge/session-log.jsonl",
    ".forge/security-audit.jsonl",
    ".forge/lessons.yaml",
    ".forge/reflections",
    ".forge/patterns.jsonl",
    "pipeline/state.md",
    "pipeline/stages.yaml",
    "pipeline/gates.yaml",
    "pipeline/decisions",
    "pipeline/log",
    "tasks/README.md",
]


def test_cli_help_runs() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Forge OS local-first lifecycle CLI" in result.output


def test_init_creates_expected_project_files() -> None:
    with runner.isolated_filesystem():
        root = Path.cwd()
        result = runner.invoke(app, ["init", "--name", "Demo", "--profile", "minimal"])

        assert result.exit_code == 0, result.output
        for relative_path in EXPECTED_INIT_PATHS:
            assert (root / relative_path).exists(), relative_path

        config = yaml.safe_load((root / ".forge" / "config.yaml").read_text(encoding="utf-8"))
        assert config["schema_version"] == "0.1"
        assert config["project"]["name"] == "Demo"
        assert config["profile"] == "minimal"
        assert config["default_adapter"] == "dummy"
        assert config["hooks"]["enabled"] is False

        state = json.loads((root / ".forge" / "state.json").read_text(encoding="utf-8"))
        assert state["schema_version"] == "0.1"
        assert state["profile"] == "minimal"
        assert state["current_stage_id"] == "srs"
        assert state["stages"][0]["status"] == "active"


def test_init_refuses_overwrite_without_force() -> None:
    with runner.isolated_filesystem():
        first = runner.invoke(app, ["init", "--name", "Demo"])
        second = runner.invoke(app, ["init", "--name", "Demo"])

        assert first.exit_code == 0, first.output
        assert second.exit_code == 1
        assert "already exists" in second.output


def test_status_reads_initialized_project() -> None:
    with runner.isolated_filesystem():
        init_result = runner.invoke(app, ["init", "--name", "Demo", "--profile", "standard"])
        status_result = runner.invoke(app, ["status"])

        assert init_result.exit_code == 0, init_result.output
        assert status_result.exit_code == 0, status_result.output
        assert "Demo" in status_result.output
        assert "standard" in status_result.output
        assert "srs" in status_result.output
        assert "0.1" in status_result.output


def test_status_handles_uninitialized_directory() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 1
        assert "No Forge project found" in result.output


def test_config_validate_accepts_generated_config() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        result = runner.invoke(app, ["config", "validate"])

        assert result.exit_code == 0, result.output
        assert "Valid Forge config" in result.output


def test_config_validate_rejects_malformed_config_file() -> None:
    with runner.isolated_filesystem():
        config_path = Path("bad-config.yaml")
        _ = config_path.write_text("schema_version: ''\nprofile: invalid\n", encoding="utf-8")

        result = runner.invoke(app, ["config", "validate", "--path", str(config_path)])

        assert result.exit_code == 1
        assert "Invalid Forge config" in result.output


def test_config_show_outputs_validated_config() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        result = runner.invoke(app, ["config", "show"])

        assert result.exit_code == 0, result.output
        assert "project:" in result.output
        assert "name: Demo" in result.output


def test_explain_known_topic() -> None:
    result = runner.invoke(app, ["explain", "security"])

    assert result.exit_code == 0
    assert "secure defaults" in result.output
