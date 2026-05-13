"""Abstract tool ID → Claude Code CLI tool name mapping."""

from __future__ import annotations

# Maps forge_os abstract tool IDs to Claude Code's --allowedTools names.
# Claude Code tool names are PascalCase as reported by the CLI.
ABSTRACT_TO_CLAUDE: dict[str, str] = {
    "read_file": "Read",
    "write_file": "Write",
    "edit_file": "Edit",
    "bash": "Bash",
    "list_files": "LS",
    "glob_files": "Glob",
    "search_code": "Grep",
    "web_fetch": "WebFetch",
    "web_search": "WebSearch",
    "todo_read": "TodoRead",
    "todo_write": "TodoWrite",
}

CLAUDE_TO_ABSTRACT: dict[str, str] = {v: k for k, v in ABSTRACT_TO_CLAUDE.items()}


def to_claude_tools(abstract_ids: list[str]) -> list[str]:
    """Convert abstract tool IDs to Claude Code tool names, dropping unknowns."""
    return [ABSTRACT_TO_CLAUDE[t] for t in abstract_ids if t in ABSTRACT_TO_CLAUDE]


def to_abstract_tools(claude_names: list[str]) -> list[str]:
    """Convert Claude Code tool names to abstract IDs, dropping unknowns."""
    return [CLAUDE_TO_ABSTRACT[t] for t in claude_names if t in CLAUDE_TO_ABSTRACT]


DEFAULT_ABSTRACT_TOOLS: list[str] = list(ABSTRACT_TO_CLAUDE.keys())
