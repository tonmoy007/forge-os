"""Tests for the HealthMonitorConfig loader (daemon-monitor S4)."""

from __future__ import annotations

from forge_os.health.monitor_config import HealthMonitorConfig, load_health_monitor_config


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
