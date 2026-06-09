"""Tests for AdapterUseCases.status (Phase 05.5 Slice 4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from forge_os.project.scaffold import initialize_project
from forge_os.use_cases.adapters import AdapterStatus, AdapterUseCases


def _project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Demo", profile="standard")
    return tmp_path


def _by_id(tmp_path: Path) -> dict[str, AdapterStatus]:
    return {s.adapter_id: s for s in AdapterUseCases(_project(tmp_path)).status()}


class TestAdapterStatus:
    def test_returns_all_adapters_in_priority_order(self, tmp_path: Path) -> None:
        statuses = AdapterUseCases(_project(tmp_path)).status()
        ids = [s.adapter_id for s in statuses]
        assert ids[0] == "dummy"
        assert "claude_code" in ids
        assert len(ids) == 9
        assert all(isinstance(s, AdapterStatus) for s in statuses)

    def test_dummy_is_default_enabled_and_available(self, tmp_path: Path) -> None:
        dummy = _by_id(tmp_path)["dummy"]
        assert dummy.is_default is True
        assert dummy.enabled is True
        assert dummy.available is True

    def test_claude_code_available_when_binary_present(self, tmp_path: Path) -> None:
        with patch("shutil.which", return_value="/usr/bin/claude"):
            cc = _by_id(tmp_path)["claude_code"]
        assert cc.available is True
        assert "stream" in cc.capabilities
        assert cc.reason == ""

    def test_claude_code_unavailable_when_binary_missing(self, tmp_path: Path) -> None:
        with patch("shutil.which", return_value=None):
            cc = _by_id(tmp_path)["claude_code"]
        assert cc.available is False
        assert "binary on PATH" in cc.reason

    def test_unregistered_adapters_marked_not_implemented(self, tmp_path: Path) -> None:
        # Mock the binary probe so the result is independent of the host
        # (claude/codex may or may not be installed) — L001 test isolation.
        with patch("shutil.which", return_value=None):
            statuses = _by_id(tmp_path)
        assert statuses["openclaw"].available is False
        assert statuses["openclaw"].reason == "not implemented"
        assert statuses["local_llm"].available is False
