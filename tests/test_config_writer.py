"""Tests for the atomic config writer (config/writer.py)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge_os.config.loader import ConfigError, load_config
from forge_os.config.writer import save_config
from forge_os.project.scaffold import initialize_project
from forge_os.schemas.config import ForgeConfig


def _config(tmp_path: Path) -> ForgeConfig:
    initialize_project(tmp_path, project_name="Demo", profile="standard")
    return load_config(tmp_path / ".forge" / "config.yaml")


class TestSaveConfig:
    def test_round_trips_through_loader(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        target = tmp_path / "out" / "config.yaml"
        save_config(target, config)
        reloaded = load_config(target)
        assert reloaded.default_adapter == config.default_adapter
        assert reloaded.adapters.keys() == config.adapters.keys()
        assert reloaded.project.name == "Demo"

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "deep" / "config.yaml"
        save_config(target, _config(tmp_path))
        assert target.exists()

    def test_overwrites_existing_without_tmp_residue(self, tmp_path: Path) -> None:
        target = tmp_path / "config.yaml"
        target.write_text("stale: true\n", encoding="utf-8")
        save_config(target, _config(tmp_path))
        # The atomic write must not strand a `.config.yaml.*.tmp` artifact.
        assert list(target.parent.glob(".config.yaml.*.tmp")) == []
        assert load_config(target).default_adapter == "dummy"

    def test_writes_schema_shaped_yaml(self, tmp_path: Path) -> None:
        target = tmp_path / "config.yaml"
        save_config(target, _config(tmp_path))
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
        # mode="json" dump keeps the schema field names the loader reads back.
        assert raw["schema_version"] == "0.1"
        assert "dummy" in raw["adapters"]

    def test_write_failure_raises_config_error_not_oserror(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        # Parent path is a regular file, so mkdir/mkstemp raise OSError; the writer
        # must surface a typed ConfigError (root can write 0444 dirs, so this is the
        # uid-independent way to force the failure under Docker-as-root).
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="Could not write config file"):
            save_config(blocker / "config.yaml", config)
