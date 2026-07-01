from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from cli_helpers import isolated_filesystem
from forge_os.adapters.claude_code.runner import ClaudeCodeSpawnError
from forge_os.cli.main import app

runner = CliRunner()


EXPECTED_INIT_PATHS = [
    ".forge/config.yaml",
    ".forge/state.json",
    ".forge/events.jsonl",
    ".forge/session-log.jsonl",
    ".forge/security-audit.jsonl",
    ".forge/traces/spans.jsonl",
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
    with isolated_filesystem():
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
    with isolated_filesystem():
        first = runner.invoke(app, ["init", "--name", "Demo"])
        second = runner.invoke(app, ["init", "--name", "Demo"])

        assert first.exit_code == 0, first.output
        assert second.exit_code == 1
        assert "already exists" in second.output


# ── Slice 6: forge init --adapter claude-code (P055.15) ─────────────────────


def test_init_with_claude_code_adapter_verifies_binary_and_writes_config() -> None:
    with isolated_filesystem():
        root = Path.cwd()
        with patch(
            "forge_os.cli.main.get_claude_version",
            return_value="2.1.170 (Claude Code)",
        ) as version_check:
            result = runner.invoke(
                app,
                ["init", "--name", "Demo", "--adapter", "claude-code",
                 "--permission-mode", "acceptEdits"],
            )

        assert result.exit_code == 0, result.output
        version_check.assert_called_once()
        assert "2.1.170" in result.output

        config = yaml.safe_load((root / ".forge" / "config.yaml").read_text(encoding="utf-8"))
        assert config["default_adapter"] == "claude_code"
        assert config["adapters"]["claude_code"]["enabled"] is True
        assert config["adapters"]["claude_code"]["permission_mode"] == "acceptEdits"
        assert config["adapters"]["dummy"]["enabled"] is False  # exactly one default enabled


def test_init_claude_code_without_permission_mode_writes_none() -> None:
    with isolated_filesystem():
        root = Path.cwd()
        with patch(
            "forge_os.cli.main.get_claude_version",
            return_value="2.1.170 (Claude Code)",
        ):
            result = runner.invoke(
                app, ["init", "--name", "Demo", "--adapter", "claude-code"]
            )

        assert result.exit_code == 0, result.output
        config = yaml.safe_load((root / ".forge" / "config.yaml").read_text(encoding="utf-8"))
        assert config["default_adapter"] == "claude_code"
        assert "permission_mode" not in config["adapters"]["claude_code"]


def test_init_claude_code_fails_when_binary_missing() -> None:
    with isolated_filesystem():
        root = Path.cwd()
        with patch(
            "forge_os.cli.main.get_claude_version",
            side_effect=ClaudeCodeSpawnError(-1, "`claude` not found on PATH."),
        ):
            result = runner.invoke(
                app, ["init", "--name", "Demo", "--adapter", "claude-code"]
            )

        assert result.exit_code == 1
        assert "claude-code adapter unavailable" in result.output
        assert not (root / ".forge").exists()  # nothing scaffolded on failure


def test_init_rejects_unknown_adapter() -> None:
    with isolated_filesystem():
        result = runner.invoke(app, ["init", "--name", "Demo", "--adapter", "bogus"])

        assert result.exit_code == 2
        assert "Unknown adapter" in result.output


def test_init_rejects_permission_mode_without_claude_code() -> None:
    with isolated_filesystem():
        result = runner.invoke(
            app, ["init", "--name", "Demo", "--permission-mode", "acceptEdits"]
        )

        assert result.exit_code == 2
        assert "only valid with --adapter claude-code" in result.output


def test_init_rejects_invalid_permission_mode() -> None:
    with isolated_filesystem():
        result = runner.invoke(
            app,
            ["init", "--name", "Demo", "--adapter", "claude-code",
             "--permission-mode", "yolo"],
        )

        assert result.exit_code == 2
        assert "Invalid permission_mode" in result.output


def test_status_reads_initialized_project() -> None:
    with isolated_filesystem():
        init_result = runner.invoke(app, ["init", "--name", "Demo", "--profile", "standard"])
        status_result = runner.invoke(app, ["status"])

        assert init_result.exit_code == 0, init_result.output
        assert status_result.exit_code == 0, status_result.output
        assert "Demo" in status_result.output
        assert "standard" in status_result.output
        assert "srs" in status_result.output
        assert "0.1" in status_result.output


def test_status_handles_uninitialized_directory() -> None:
    with isolated_filesystem():
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 1
        assert "No Forge project found" in result.output


def test_config_validate_accepts_generated_config() -> None:
    with isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        result = runner.invoke(app, ["config", "validate"])

        assert result.exit_code == 0, result.output
        assert "Valid Forge config" in result.output


def test_config_validate_rejects_malformed_config_file() -> None:
    with isolated_filesystem():
        config_path = Path("bad-config.yaml")
        _ = config_path.write_text("schema_version: ''\nprofile: invalid\n", encoding="utf-8")

        result = runner.invoke(app, ["config", "validate", "--path", str(config_path)])
        assert result.exit_code == 1
        assert "Invalid Forge config" in str(result.exception)


def test_config_show_outputs_validated_config() -> None:
    with isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        result = runner.invoke(app, ["config", "show"])

        assert result.exit_code == 0, result.output
        assert "project:" in result.output
        assert "name: Demo" in result.output


def test_explain_known_topic() -> None:
    result = runner.invoke(app, ["explain", "security"])

    assert result.exit_code == 0
    assert "Phase 01 uses secure defaults" in result.output
    assert "security profiles" in result.output


def test_status_renders_daemon_alerts_when_present() -> None:
    # P10.11 / FR-BD-002: alerts surface in `forge status`.
    fake_alerts = [
        {
            "severity": "warning",
            "source": "acp-registry",
            "message": "ACP registry is not accessible",
            "created_at": "2026-06-10T12:00:00Z",
        }
    ]
    with isolated_filesystem():
        _ = runner.invoke(app, ["init", "--name", "Demo"])
        with patch("forge_os.cli.main.daemon_alerts", return_value=fake_alerts):
            result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, result.output
    assert "Daemon Alerts" in result.output
    assert "acp-registry" in result.output


def test_status_omits_alert_table_when_no_alerts() -> None:
    with isolated_filesystem():
        _ = runner.invoke(app, ["init", "--name", "Demo"])
        with patch("forge_os.cli.main.daemon_alerts", return_value=[]):
            result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, result.output
    assert "Daemon Alerts" not in result.output
