"""Tests for token-budget monitoring wired into the stage executor (FR-HD-003)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from forge_os.agents import executor
from forge_os.agents.executor import _monitor_token_budget, run_stage_agent, run_stage_agent_async
from forge_os.project.scaffold import initialize_project
from forge_os.project.status import load_state


def _project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Demo", profile="minimal")
    return tmp_path


def _budget_events(root: Path) -> list[dict]:
    path = root / ".forge" / "events.jsonl"
    if not path.exists():
        return []
    return [
        event
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        if (event := json.loads(line))["event_type"] == "TokenBudgetExceeded"
    ]


def _selection(total_tokens: int, token_budget: int = 2000) -> SimpleNamespace:
    return SimpleNamespace(
        total_tokens=total_tokens, token_budget=token_budget, selection_id="sel-1"
    )


class TestMonitorHelper:
    def test_emits_event_on_warn(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _monitor_token_budget(root, "build", _selection(1700))  # 0.85
        events = _budget_events(root)
        assert len(events) == 1
        assert events[0]["payload"]["level"] == "warn"
        assert events[0]["payload"]["total_tokens"] == 1700
        assert events[0]["stage_id"] == "build"

    def test_emits_event_on_error(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _monitor_token_budget(root, "build", _selection(2000))  # 1.0
        events = _budget_events(root)
        assert len(events) == 1
        assert events[0]["payload"]["level"] == "error"

    def test_no_event_when_ok(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _monitor_token_budget(root, "build", _selection(500))  # 0.25
        assert _budget_events(root) == []

    def test_never_raises_when_event_write_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _project(tmp_path)

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr("forge_os.events.log.append_event", _boom)
        _monitor_token_budget(root, "build", _selection(1900))  # must not raise

    def test_config_warn_ratio_lowers_threshold(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _project(tmp_path)
        monkeypatch.setattr(
            "forge_os.config.loader.load_config",
            lambda _path: SimpleNamespace(features={"token_monitor": {"warn_ratio": 0.4}}),
        )
        _monitor_token_budget(root, "build", _selection(1000))  # 0.5 >= 0.4 -> warn
        events = _budget_events(root)
        assert len(events) == 1
        assert events[0]["payload"]["level"] == "warn"

    def test_degrades_when_config_yaml_corrupt(self, tmp_path: Path) -> None:
        # Real loader ConfigError path: a corrupt config.yaml must fall back to the
        # default warn_ratio and still grade/emit, never break the spawn.
        root = _project(tmp_path)
        (root / ".forge" / "config.yaml").write_text("{[ not valid yaml", encoding="utf-8")
        _monitor_token_budget(root, "build", _selection(1700))  # 0.85 vs default 0.80
        events = _budget_events(root)
        assert len(events) == 1
        assert events[0]["payload"]["level"] == "warn"

    def test_degrades_when_config_raises_schema_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Regression (L011): ForgeConfig validators raise schemas.config.ConfigError
        # (a plain Exception, not the loader's RuntimeError ConfigError); it must not
        # escape the best-effort monitor and break the spawn.
        from forge_os.schemas.config import ConfigError as SchemaConfigError

        root = _project(tmp_path)

        def _raise(_path: Path) -> object:
            raise SchemaConfigError("schema_version must be present")

        monkeypatch.setattr("forge_os.config.loader.load_config", _raise)
        _monitor_token_budget(root, "build", _selection(1700))  # must not raise
        events = _budget_events(root)
        assert len(events) == 1
        assert events[0]["payload"]["level"] == "warn"


class TestExecutorWiring:
    def test_run_stage_agent_invokes_monitor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _project(tmp_path)
        state = load_state(root)
        calls: list[str] = []
        monkeypatch.setattr(
            executor,
            "_monitor_token_budget",
            lambda _root, stage_id, _selection: calls.append(stage_id),
        )
        run_stage_agent(root, state, "srs")
        assert calls == ["srs"]

    async def test_run_stage_agent_async_invokes_monitor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _project(tmp_path)
        state = load_state(root)
        calls: list[str] = []
        monkeypatch.setattr(
            executor,
            "_monitor_token_budget",
            lambda _root, stage_id, _selection: calls.append(stage_id),
        )
        await run_stage_agent_async(root, state, "srs")
        assert calls == ["srs"]

    async def test_async_spawn_survives_schema_invalid_config(self, tmp_path: Path) -> None:
        # End-to-end regression (L011) for the exact confirmed bug: a whitespace
        # schema_version makes load_config raise schemas.config.ConfigError on the
        # async path (the monitor's only config load); the spawn must still complete.
        import yaml

        root = _project(tmp_path)
        config_path = root / ".forge" / "config.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["schema_version"] = "   "
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

        record = await run_stage_agent_async(root, load_state(root), "srs")
        assert record.status == "completed"
