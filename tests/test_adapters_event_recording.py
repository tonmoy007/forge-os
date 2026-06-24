"""Tests for F0: wiring the project Event Store into the production spawn path.

Before F0, spawn cost/usage events were recorded only when `event_store` was
injected in tests — the production factory never passed it, so a real
`forge agent run` recorded nothing. These tests pin the wiring.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_os.adapters.claude_code.adapter import ClaudeCodeAdapter
from forge_os.adapters.dummy import DummyAdapter
from forge_os.adapters.registry import create_adapter_from_config
from forge_os.agents import executor
from forge_os.agents.executor import run_stage_agent
from forge_os.config.loader import load_config
from forge_os.events.store import EventStore
from forge_os.project.scaffold import initialize_project
from forge_os.project.status import load_state


def _claude_project(tmp_path: Path) -> Path:
    initialize_project(
        tmp_path, project_name="Demo", profile="minimal", default_adapter="claude_code"
    )
    return tmp_path


class TestBindEventStore:
    def test_noop_on_non_recording_adapter(self, tmp_path: Path) -> None:
        event_store = EventStore(tmp_path / "events.db")
        # DummyAdapter inherits the no-op default — binding must not raise.
        DummyAdapter(tmp_path).bind_event_store(event_store)

    def test_claude_code_captures_store(self, tmp_path: Path) -> None:
        event_store = EventStore(tmp_path / "events.db")
        adapter = ClaudeCodeAdapter(tmp_path)
        assert adapter._event_store is None
        adapter.bind_event_store(event_store)
        assert adapter._event_store is event_store


class TestFactoryWiring:
    def test_binds_event_store_when_provided(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _claude_project(tmp_path)
        config = load_config(root / ".forge" / "config.yaml")
        event_store = EventStore(root / "events.db")
        monkeypatch.setattr("shutil.which", lambda _bin: "/usr/bin/claude")
        adapter = create_adapter_from_config(root, config, event_store=event_store)
        assert adapter._event_store is event_store

    def test_no_store_leaves_adapter_unbound(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _claude_project(tmp_path)
        config = load_config(root / ".forge" / "config.yaml")
        monkeypatch.setattr("shutil.which", lambda _bin: "/usr/bin/claude")
        adapter = create_adapter_from_config(root, config)
        assert adapter._event_store is None


class _RecordingAdapter(DummyAdapter):
    """Stands in for a recording adapter (claude_code needs the `claude` binary)."""

    def bind_event_store(self, event_store: object) -> None:
        self._recording_store = event_store

    def spawn_agent(self, persona, context, tools):  # type: ignore[no-untyped-def]
        handle = super().spawn_agent(persona, context, tools)
        self._recording_store.append("run-rec", "AdapterSpawnCompleted", {"adapter": "rec"})
        return handle


class TestExecutorRecording:
    def test_run_stage_agent_records_spawn_completed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        initialize_project(tmp_path, project_name="Demo", profile="minimal")
        state = load_state(tmp_path)

        def _fake_create(project_root, config, *, event_store=None):  # type: ignore[no-untyped-def]
            adapter = _RecordingAdapter(project_root)
            adapter.bind_event_store(event_store)
            return adapter

        monkeypatch.setattr(executor, "create_adapter_from_config", _fake_create)
        run_stage_agent(tmp_path, state, "srs")

        # The executor opened the project's events.db and passed it to the adapter,
        # which recorded to it — so a fresh store on the same file sees the event.
        recorded = EventStore(tmp_path / ".forge" / "events.db").read_by_type(
            "AdapterSpawnCompleted"
        )
        assert len(recorded) == 1

    def test_default_dummy_spawn_unaffected_by_wiring(self, tmp_path: Path) -> None:
        # The default (dummy) adapter is a no-op recorder, so the F0 wiring must
        # leave the normal spawn path working and record nothing.
        initialize_project(tmp_path, project_name="Demo", profile="minimal")
        record = run_stage_agent(tmp_path, load_state(tmp_path), "srs")
        assert record.status == "completed"
        recorded = EventStore(tmp_path / ".forge" / "events.db").read_by_type(
            "AdapterSpawnCompleted"
        )
        assert recorded == []
