"""ClaudeCodeAdapter — Phase 05.5 real kernel adapter."""

from forge_os.adapters.claude_code.adapter import ClaudeCodeAdapter
from forge_os.adapters.claude_code.hooks import (
    ClaudeSettingsError,
    ClaudeSettingsHookWriter,
)
from forge_os.adapters.claude_code.replay import ReplayError, replay_session
from forge_os.adapters.claude_code.runner import ClaudeCodeSpawnError

__all__ = [
    "ClaudeCodeAdapter",
    "ClaudeCodeSpawnError",
    "ClaudeSettingsError",
    "ClaudeSettingsHookWriter",
    "ReplayError",
    "replay_session",
]
