"""Tests for AdapterUseCases.status (Phase 05.5 Slice 4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from forge_os.adapters.registry import AdapterRegistryError
from forge_os.config.loader import load_config
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
        # local_llm is still a registered-but-unimplemented placeholder.
        assert statuses["local_llm"].available is False
        assert statuses["local_llm"].reason == "not implemented"

    def test_openclaw_registered_but_needs_gateway(self, tmp_path: Path) -> None:
        # Phase 11 S3: openclaw is now implemented but unavailable until a gateway
        # endpoint is configured — it is no longer a "not implemented" placeholder.
        with patch("shutil.which", return_value=None):
            openclaw = _by_id(tmp_path)["openclaw"]
        assert openclaw.available is False
        assert "gateway endpoint" in openclaw.reason


class TestAdapterSetEnabled:
    def test_enable_flips_and_persists(self, tmp_path: Path) -> None:
        uc = AdapterUseCases(_project(tmp_path))
        result = uc.set_enabled("human", enabled=True)
        assert result.enabled is True
        assert result.changed is True
        reloaded = load_config(tmp_path / ".forge" / "config.yaml")
        assert reloaded.adapters["human"]["enabled"] is True

    def test_re_enable_is_idempotent(self, tmp_path: Path) -> None:
        uc = AdapterUseCases(_project(tmp_path))
        uc.set_enabled("human", enabled=True)
        again = uc.set_enabled("human", enabled=True)
        assert again.enabled is True
        assert again.changed is False  # already in the requested state ⇒ no rewrite

    def test_make_default_sets_default_and_forces_enabled(self, tmp_path: Path) -> None:
        uc = AdapterUseCases(_project(tmp_path))
        # enabled=False is overridden because a default must be selectable.
        result = uc.set_enabled("human", enabled=False, make_default=True)
        assert result.is_default is True
        assert result.enabled is True
        config = load_config(tmp_path / ".forge" / "config.yaml")
        assert config.default_adapter == "human"
        assert config.adapters["human"]["enabled"] is True

    def test_disable_non_default_flips_back(self, tmp_path: Path) -> None:
        uc = AdapterUseCases(_project(tmp_path))
        uc.set_enabled("human", enabled=True)
        result = uc.set_enabled("human", enabled=False)
        assert result.enabled is False
        config = load_config(tmp_path / ".forge" / "config.yaml")
        assert config.adapters["human"]["enabled"] is False

    def test_disabling_the_default_is_refused(self, tmp_path: Path) -> None:
        uc = AdapterUseCases(_project(tmp_path))  # dummy is the scaffolded default
        with pytest.raises(AdapterRegistryError, match="default adapter"):
            uc.set_enabled("dummy", enabled=False)
        # The guard must not have mutated config on the way out.
        assert load_config(tmp_path / ".forge" / "config.yaml").adapters["dummy"]["enabled"] is True

    def test_unknown_adapter_raises(self, tmp_path: Path) -> None:
        uc = AdapterUseCases(_project(tmp_path))
        with pytest.raises(AdapterRegistryError, match="Unknown adapter"):
            uc.set_enabled("bogus", enabled=True)

    def test_enabling_unavailable_adapter_reports_reason(self, tmp_path: Path) -> None:
        uc = AdapterUseCases(_project(tmp_path))
        with patch("shutil.which", return_value=None):  # no `claude` binary on PATH
            result = uc.set_enabled("claude_code", enabled=True)
        assert result.enabled is True  # config write still succeeds
        assert result.available is False
        assert "binary on PATH" in result.reason

    def test_change_is_visible_to_status(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        AdapterUseCases(root).set_enabled("human", enabled=True, make_default=True)
        statuses = {s.adapter_id: s for s in AdapterUseCases(root).status()}
        assert statuses["human"].enabled is True
        assert statuses["human"].is_default is True
        assert statuses["dummy"].is_default is False
