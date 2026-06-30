"""CLI tests for `forge adapter enable/disable` (FR-KA-003)."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from cli_helpers import isolated_filesystem
from forge_os.cli.main import app

runner = CliRunner()


def _init() -> Path:
    result = runner.invoke(app, ["init", "--name", "Demo", "--profile", "minimal"])
    assert result.exit_code == 0, result.output
    return Path.cwd()


def _config(root: Path) -> dict:
    return yaml.safe_load((root / ".forge" / "config.yaml").read_text(encoding="utf-8"))


def test_enable_flips_enabled_flag() -> None:
    with isolated_filesystem():
        root = _init()
        result = runner.invoke(app, ["adapter", "enable", "human"])
        assert result.exit_code == 0, result.output
        assert "enabled" in result.output
        assert _config(root)["adapters"]["human"]["enabled"] is True


def test_enable_default_switches_kernel() -> None:
    with isolated_filesystem():
        root = _init()
        result = runner.invoke(app, ["adapter", "enable", "human", "--default"])
        assert result.exit_code == 0, result.output
        config = _config(root)
        assert config["default_adapter"] == "human"
        assert config["adapters"]["human"]["enabled"] is True


def test_disable_default_is_refused() -> None:
    with isolated_filesystem():
        root = _init()
        result = runner.invoke(app, ["adapter", "disable", "dummy"])
        assert result.exit_code == 1
        assert "default adapter" in result.output
        # The refused write must leave dummy enabled + default untouched.
        assert _config(root)["adapters"]["dummy"]["enabled"] is True


def test_unknown_adapter_is_rejected() -> None:
    with isolated_filesystem():
        _init()
        result = runner.invoke(app, ["adapter", "enable", "bogus"])
        assert result.exit_code == 1
        assert "Unknown adapter" in result.output


def test_disable_non_default_adapter() -> None:
    with isolated_filesystem():
        root = _init()
        runner.invoke(app, ["adapter", "enable", "human"])
        result = runner.invoke(app, ["adapter", "disable", "human"])
        assert result.exit_code == 0, result.output
        assert _config(root)["adapters"]["human"]["enabled"] is False


def test_enable_accepts_kebab_case_id() -> None:
    with isolated_filesystem():
        root = _init()
        # `forge init --adapter claude-code` accepts kebab-case; enable must too.
        result = runner.invoke(app, ["adapter", "enable", "claude-code"])
        assert result.exit_code == 0, result.output
        assert _config(root)["adapters"]["claude_code"]["enabled"] is True


def test_list_reflects_enable_as_default() -> None:
    with isolated_filesystem():
        _init()
        enabled = runner.invoke(app, ["adapter", "enable", "human", "--default"])
        assert enabled.exit_code == 0, enabled.output

        listing = runner.invoke(app, ["adapter", "list"])
        assert listing.exit_code == 0, listing.output
        # The Default column ("yes") must move onto the human row and off dummy —
        # `human` alone always renders, so assert the rendered default marker.
        human_row = next(ln for ln in listing.output.splitlines() if " human " in ln)
        dummy_row = next(ln for ln in listing.output.splitlines() if " dummy " in ln)
        assert "yes" in human_row
        assert "yes" not in dummy_row
