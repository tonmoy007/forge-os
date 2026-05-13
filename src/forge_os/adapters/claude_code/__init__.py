"""ClaudeCodeAdapter — Phase 05.5 real kernel adapter."""

from forge_os.adapters.claude_code.adapter import ClaudeCodeAdapter
from forge_os.adapters.claude_code.runner import ClaudeCodeSpawnError

__all__ = ["ClaudeCodeAdapter", "ClaudeCodeSpawnError"]
