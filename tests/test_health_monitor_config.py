"""Tests for the HealthMonitorConfig loader (daemon-monitor S4)."""

from __future__ import annotations

from pathlib import Path

from forge_os.health.monitor_config import (
    HealthMonitorConfig,
    load_health_monitor_config,
    resolve_cost_cap_usd,
)


def _write_config(project_root: Path, features_block: str) -> None:
    forge = project_root / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "config.yaml").write_text(
        "schema_version: '0.1'\nproject:\n  name: demo\n" + features_block,
        encoding="utf-8",
    )


class TestLoadHealthMonitorConfig:
    def test_missing_section_defaults_off_and_uncapped(self) -> None:
        assert load_health_monitor_config({}) == HealthMonitorConfig()

    def test_non_dict_section_defaults(self) -> None:
        assert load_health_monitor_config({"health_monitor": "nope"}) == HealthMonitorConfig()

    def test_reads_enabled_and_cap(self) -> None:
        cfg = load_health_monitor_config({"health_monitor": {"enabled": True, "cost_cap_usd": 5.0}})
        assert cfg.enabled is True
        assert cfg.cost_cap_usd == 5.0

    def test_int_cap_is_coerced_to_float(self) -> None:
        cfg = load_health_monitor_config({"health_monitor": {"cost_cap_usd": 10}})
        assert cfg.cost_cap_usd == 10.0

    def test_non_positive_cap_is_none(self) -> None:
        for bad in (0, -5, 0.0):
            assert load_health_monitor_config(
                {"health_monitor": {"cost_cap_usd": bad}}
            ).cost_cap_usd is None

    def test_malformed_cap_is_none(self) -> None:
        for bad in ("lots", None, True, [1], {"x": 1}):
            assert load_health_monitor_config(
                {"health_monitor": {"cost_cap_usd": bad}}
            ).cost_cap_usd is None

    def test_non_bool_enabled_falls_back_to_false(self) -> None:
        assert load_health_monitor_config({"health_monitor": {"enabled": "yes"}}).enabled is False


class TestResolveCostCapUsd:
    def test_resolves_cap_from_config(self, tmp_path: Path) -> None:
        _write_config(tmp_path, "features:\n  health_monitor:\n    cost_cap_usd: 7.5\n")
        assert resolve_cost_cap_usd(tmp_path) == 7.5

    def test_missing_config_file_is_none(self, tmp_path: Path) -> None:
        # No .forge/config.yaml at all ⇒ uncapped (load_config wraps the missing
        # file as ConfigError, which resolve_cost_cap_usd swallows).
        assert resolve_cost_cap_usd(tmp_path) is None

    def test_no_health_monitor_section_is_none(self, tmp_path: Path) -> None:
        _write_config(tmp_path, "features:\n  observer: false\n")
        assert resolve_cost_cap_usd(tmp_path) is None

    def test_broken_config_is_none(self, tmp_path: Path) -> None:
        forge = tmp_path / ".forge"
        forge.mkdir(parents=True, exist_ok=True)
        (forge / "config.yaml").write_text("just a string, not a mapping\n", encoding="utf-8")
        assert resolve_cost_cap_usd(tmp_path) is None
