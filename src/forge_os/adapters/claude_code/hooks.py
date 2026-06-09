"""Claude Code `.claude/settings.json` hook lifecycle management.

The ClaudeCodeAdapter can register PreToolUse / PostToolUse hooks so that the
``claude`` subprocess notifies an external command on every tool invocation.
This module owns the write/merge/restore lifecycle of that settings file so the
adapter never leaves a project's `.claude/settings.json` mutated after a run.

The hook command is injected by the caller — this module does not assume any
particular ``forge`` subcommand exists.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import TracebackType
from typing import Any

log = logging.getLogger("forge.kernel.claude_code")


class ClaudeSettingsError(RuntimeError):
    """Raised when an existing `.claude/settings.json` cannot be parsed."""


def _hook_block(command: str, matcher: str) -> dict[str, Any]:
    """Build a single Claude Code hook entry for one event type."""
    return {
        "matcher": matcher,
        "hooks": [{"type": "command", "command": command}],
    }


class ClaudeSettingsHookWriter:
    """Context manager that installs tool-use hooks into `.claude/settings.json`.

    On enter it merges PreToolUse/PostToolUse hook entries (pointing at the
    caller-supplied commands) into the project's `.claude/settings.json`,
    preserving any pre-existing keys and hooks. On exit it restores the file to
    exactly its prior state — original bytes if the file existed, or removed
    entirely (along with a `.claude/` directory this writer created) if it did
    not. Teardown runs even if the wrapped block raises.

    One instance manages one install/restore cycle (the adapter creates a fresh
    instance per spawn). `restore()` is resilient: a filesystem failure during
    teardown is logged, never raised, so it cannot mask the wrapped block's
    outcome.
    """

    def __init__(
        self,
        project_root: Path | str,
        *,
        pre_tool_command: str,
        post_tool_command: str,
        matcher: str = "*",
    ) -> None:
        self.project_root = Path(project_root)
        self.pre_tool_command = pre_tool_command
        self.post_tool_command = post_tool_command
        self.matcher = matcher

        self._claude_dir = self.project_root / ".claude"
        self._settings_path = self._claude_dir / "settings.json"
        self._original_text: str | None = None
        self._created_claude_dir = False

    def __enter__(self) -> ClaudeSettingsHookWriter:
        self.install()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.restore()

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def install(self) -> None:
        """Merge hook entries into `.claude/settings.json`, capturing prior state."""
        if not self._claude_dir.exists():
            self._claude_dir.mkdir(parents=True)
            self._created_claude_dir = True

        if self._settings_path.exists():
            self._original_text = self._settings_path.read_text(encoding="utf-8")
            settings = self._load_settings(self._original_text)
        else:
            self._original_text = None
            settings = {}

        merged = self._merge_hooks(settings)
        self._settings_path.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def restore(self) -> None:
        """Restore `.claude/settings.json` to its pre-install state.

        Resilient by design: a filesystem error during teardown (disk full,
        permissions, a concurrent mutation of `.claude/` between the emptiness
        check and ``rmdir``) is logged and swallowed so it can never mask the
        outcome of the block this context manager wrapped.
        """
        try:
            if self._original_text is not None:
                self._settings_path.write_text(self._original_text, encoding="utf-8")
                return

            self._settings_path.unlink(missing_ok=True)
            if (
                self._created_claude_dir
                and self._claude_dir.exists()
                and not any(self._claude_dir.iterdir())
            ):
                self._claude_dir.rmdir()
                self._created_claude_dir = False
        except OSError as exc:
            log.warning("failed to restore %s: %s", self._settings_path, exc)

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _load_settings(text: str) -> dict[str, Any]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ClaudeSettingsError(
                f"existing .claude/settings.json is not valid JSON: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise ClaudeSettingsError(".claude/settings.json must contain a JSON object")
        return data

    def _merge_hooks(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Append our hook entries without clobbering existing keys or hooks."""
        merged = dict(settings)
        hooks = dict(merged.get("hooks", {}))
        pre = list(hooks.get("PreToolUse", []))
        post = list(hooks.get("PostToolUse", []))
        pre.append(_hook_block(self.pre_tool_command, self.matcher))
        post.append(_hook_block(self.post_tool_command, self.matcher))
        hooks["PreToolUse"] = pre
        hooks["PostToolUse"] = post
        merged["hooks"] = hooks
        return merged
