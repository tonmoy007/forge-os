"""Tests for the tracing config loader (FR-OBS-001, FR-SEM-002 — S2)."""

from __future__ import annotations

from pathlib import Path

import yaml

from forge_os.tracing.config import (
    TracingConfig,
    load_tracing_config,
    load_tracing_config_from_project,
)


def test_default_is_disabled_when_section_absent() -> None:
    config = load_tracing_config({})

    assert config == TracingConfig(enabled=False, otlp_endpoint=None)


def test_bare_true_enables_with_defaults() -> None:
    config = load_tracing_config({"tracing": True})

    assert config.enabled is True
    assert config.otlp_endpoint is None


def test_bare_false_stays_disabled() -> None:
    assert load_tracing_config({"tracing": False}).enabled is False


def test_mapping_enabled_and_endpoint() -> None:
    config = load_tracing_config(
        {"tracing": {"enabled": True, "otlp_endpoint": "http://localhost:4317"}}
    )

    assert config.enabled is True
    assert config.otlp_endpoint == "http://localhost:4317"


def test_endpoint_without_enabled_defaults_disabled() -> None:
    # An endpoint alone does not enable local-sink emission; `enabled` is the gate.
    config = load_tracing_config({"tracing": {"otlp_endpoint": "http://collector:4317"}})

    assert config.enabled is False
    assert config.otlp_endpoint == "http://collector:4317"


def test_blank_endpoint_is_normalized_to_none() -> None:
    config = load_tracing_config({"tracing": {"enabled": True, "otlp_endpoint": "   "}})

    assert config.otlp_endpoint is None


def test_non_string_endpoint_is_ignored() -> None:
    config = load_tracing_config({"tracing": {"enabled": True, "otlp_endpoint": 4317}})

    assert config.otlp_endpoint is None


def test_non_bool_enabled_falls_back_to_disabled() -> None:
    # `features` is unvalidated free-form; a garbage `enabled` must not crash or
    # accidentally enable tracing.
    config = load_tracing_config({"tracing": {"enabled": "yes"}})

    assert config.enabled is False


def test_garbage_section_type_defaults_disabled() -> None:
    assert load_tracing_config({"tracing": "on"}).enabled is False
    assert load_tracing_config({"tracing": ["x"]}).enabled is False


def _write_config(project_root: Path, features: dict) -> None:
    (project_root / ".forge").mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": "0.1",
        "project": {"name": "demo"},
        "profile": "minimal",
        "default_adapter": "dummy",
        "features": features,
    }
    (project_root / ".forge" / "config.yaml").write_text(
        yaml.safe_dump(doc), encoding="utf-8"
    )


def test_from_project_reads_features(tmp_path: Path) -> None:
    _write_config(tmp_path, {"tracing": {"enabled": True, "otlp_endpoint": "http://c:4317"}})

    config = load_tracing_config_from_project(tmp_path)

    assert config.enabled is True
    assert config.otlp_endpoint == "http://c:4317"


def test_from_project_missing_config_defaults_disabled(tmp_path: Path) -> None:
    # No `.forge/config.yaml` at all → disabled, never raises.
    assert load_tracing_config_from_project(tmp_path).enabled is False


def test_from_project_broken_config_defaults_disabled(tmp_path: Path) -> None:
    (tmp_path / ".forge").mkdir(parents=True)
    (tmp_path / ".forge" / "config.yaml").write_text("{not: valid: yaml:", encoding="utf-8")

    assert load_tracing_config_from_project(tmp_path).enabled is False
