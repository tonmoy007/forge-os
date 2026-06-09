"""Tests for ClaudeSettingsHookWriter — `.claude/settings.json` hook lifecycle."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge_os.adapters.claude_code.hooks import (
    ClaudeSettingsError,
    ClaudeSettingsHookWriter,
)


def _read_settings(root: Path) -> dict:
    return json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))


def _writer(root: Path, **kwargs: str) -> ClaudeSettingsHookWriter:
    params = {"pre_tool_command": "forge hook pre", "post_tool_command": "forge hook post"}
    params.update(kwargs)
    return ClaudeSettingsHookWriter(root, **params)  # type: ignore[arg-type]


# ── Install ──────────────────────────────────────────────────────────────────


class TestInstall:
    def test_creates_settings_with_pre_and_post_hooks(self, tmp_path: Path) -> None:
        with _writer(tmp_path):
            data = _read_settings(tmp_path)
            pre = data["hooks"]["PreToolUse"][0]
            post = data["hooks"]["PostToolUse"][0]
            assert pre["matcher"] == "*"
            assert pre["hooks"][0] == {"type": "command", "command": "forge hook pre"}
            assert post["hooks"][0] == {"type": "command", "command": "forge hook post"}

    def test_custom_matcher(self, tmp_path: Path) -> None:
        with _writer(tmp_path, matcher="Bash"):
            data = _read_settings(tmp_path)
            assert data["hooks"]["PreToolUse"][0]["matcher"] == "Bash"

    def test_settings_file_is_valid_json_with_trailing_newline(self, tmp_path: Path) -> None:
        with _writer(tmp_path):
            text = (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8")
            assert text.endswith("\n")
            json.loads(text)  # parses


# ── Restore ──────────────────────────────────────────────────────────────────


class TestRestore:
    def test_removes_created_file_and_dir(self, tmp_path: Path) -> None:
        with _writer(tmp_path):
            assert (tmp_path / ".claude" / "settings.json").exists()
        assert not (tmp_path / ".claude" / "settings.json").exists()
        assert not (tmp_path / ".claude").exists()

    def test_restores_prior_settings_byte_for_byte(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        original = {
            "permissions": {"allow": ["Read"]},
            "hooks": {"Stop": [{"matcher": "*", "hooks": []}]},
        }
        original_text = json.dumps(original, indent=2)
        (claude_dir / "settings.json").write_text(original_text, encoding="utf-8")

        with _writer(tmp_path):
            merged = _read_settings(tmp_path)
            assert merged["permissions"] == {"allow": ["Read"]}
            assert "Stop" in merged["hooks"]  # unrelated hook preserved during run
            assert merged["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "forge hook pre"

        # restored exactly to the original bytes
        assert (claude_dir / "settings.json").read_text(encoding="utf-8") == original_text

    def test_preserves_preexisting_claude_dir(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text("{}", encoding="utf-8")
        with _writer(tmp_path):
            pass
        assert claude_dir.exists()  # not removed — the writer did not create it
        assert _read_settings(tmp_path) == {}

    def test_restores_even_when_block_raises(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="boom"):
            with _writer(tmp_path):
                assert (tmp_path / ".claude" / "settings.json").exists()
                raise RuntimeError("boom")
        assert not (tmp_path / ".claude").exists()

    def test_appends_to_existing_pre_tool_hooks(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        original = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Edit", "hooks": [{"type": "command", "command": "existing"}]}
                ]
            }
        }
        (claude_dir / "settings.json").write_text(json.dumps(original), encoding="utf-8")
        with _writer(tmp_path):
            commands = [
                h["hooks"][0]["command"] for h in _read_settings(tmp_path)["hooks"]["PreToolUse"]
            ]
            assert "existing" in commands  # not clobbered
            assert "forge hook pre" in commands  # appended


# ── Invalid settings ─────────────────────────────────────────────────────────


class TestInvalidSettings:
    def test_raises_on_malformed_json(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(ClaudeSettingsError):
            _writer(tmp_path).install()

    def test_raises_on_non_object_json(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ClaudeSettingsError):
            _writer(tmp_path).install()


# ── Restore resilience ───────────────────────────────────────────────────────


class TestRestoreResilience:
    def test_restore_failure_is_logged_not_raised(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Pre-existing settings → restore takes the write_text branch.
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text("{}", encoding="utf-8")
        writer = _writer(tmp_path)
        writer.install()

        def boom(*_args: object, **_kwargs: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(Path, "write_text", boom)
        with caplog.at_level("WARNING"):
            writer.restore()  # must not raise — cleanup is resilient
        assert "failed to restore" in caplog.text

    def test_restore_failure_does_not_mask_block_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text("{}", encoding="utf-8")
        writer = _writer(tmp_path)

        def boom(*_args: object, **_kwargs: object) -> None:
            raise OSError("disk full")

        # install() succeeds (write_text not yet patched); the teardown write
        # fails but is swallowed, so the block's ValueError must still surface.
        with pytest.raises(ValueError, match="block error"):
            with writer:
                monkeypatch.setattr(Path, "write_text", boom)
                raise ValueError("block error")
