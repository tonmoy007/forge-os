"""Claude Code CLI subprocess invocation and stream-json line parser.

The CLI (`claude -p … --output-format stream-json --verbose`) emits one JSON
object per line. Verified against claude 2.1.x, each line is an envelope:

    {"type": "system", "subtype": "init", ...}        session metadata
    {"type": "assistant", "message": {"content": [     one assistant turn
        {"type": "text", "text": "..."},
        {"type": "tool_use", "id": "...", "name": "Read", "input": {...}}]}}
    {"type": "user", "message": {"content": [          tool results fed back
        {"type": "tool_result", "tool_use_id": "...", "content": "..."}]}}
    {"type": "result", "subtype": "success"|"error_*", "is_error": false,
     "result": "<final text>", "usage": {...}, "total_cost_usd": 0.0, ...}

Text lives at ``message.content[].text`` (NOT a top-level ``content`` field) and
the agent's final answer is the ``result`` line's ``result`` field. Other line
types (``rate_limit_event``, ``system`` hook subtypes) carry no adapter payload
and are recorded verbatim but otherwise ignored.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ClaudeCodeSpawnError(RuntimeError):
    """Raised when the claude subprocess exits non-zero or reports an error."""

    def __init__(self, returncode: int, stderr: str) -> None:
        super().__init__(f"claude exited {returncode}: {stderr.strip()[:200]}")
        self.returncode = returncode
        self.stderr = stderr


@dataclass
class StreamEvent:
    """One parsed stream-json line; ``type`` is the top-level envelope type."""

    type: str
    raw: dict[str, Any]

    @property
    def _content_blocks(self) -> list[dict[str, Any]]:
        """Content blocks of an assistant/user message (``[]`` for other lines)."""
        message = self.raw.get("message")
        if isinstance(message, dict):
            blocks = message.get("content")
            if isinstance(blocks, list):
                return [b for b in blocks if isinstance(b, dict)]
        return []

    @property
    def text(self) -> str:
        """Concatenated text of an assistant message (``''`` for other lines)."""
        return "".join(b.get("text", "") for b in self._content_blocks if b.get("type") == "text")

    @property
    def tool_use_blocks(self) -> list[dict[str, Any]]:
        """`tool_use` content blocks of an assistant message."""
        return [b for b in self._content_blocks if b.get("type") == "tool_use"]


@dataclass
class RunResult:
    """Aggregated result of a claude subprocess run."""

    returncode: int
    events: list[StreamEvent] = field(default_factory=list)
    stderr: str = ""

    @property
    def _result_event(self) -> StreamEvent | None:
        for event in reversed(self.events):
            if event.type == "result":
                return event
        return None

    @property
    def text_output(self) -> str:
        """The agent's final text — the ``result`` line, else assistant turns."""
        result = self._result_event
        if result is not None and isinstance(result.raw.get("result"), str):
            return result.raw["result"]
        return "\n".join(e.text for e in self.events if e.type == "assistant" and e.text)

    @property
    def tool_uses(self) -> list[dict[str, Any]]:
        """Every ``tool_use`` block across all assistant turns."""
        blocks: list[dict[str, Any]] = []
        for event in self.events:
            if event.type == "assistant":
                blocks.extend(event.tool_use_blocks)
        return blocks

    @property
    def usage(self) -> dict[str, Any]:
        result = self._result_event
        if result is not None and isinstance(result.raw.get("usage"), dict):
            return result.raw["usage"]
        return {}

    @property
    def total_cost_usd(self) -> float | None:
        result = self._result_event
        if result is not None and isinstance(result.raw.get("total_cost_usd"), int | float):
            return float(result.raw["total_cost_usd"])
        return None

    @property
    def is_error(self) -> bool:
        result = self._result_event
        return bool(result.raw.get("is_error")) if result is not None else False

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.is_error


def _parse_stream_lines(stdout: str) -> Iterator[StreamEvent]:
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        yield StreamEvent(type=obj.get("type", "unknown"), raw=obj)


def _error_summary(result: RunResult) -> str:
    event = result._result_event
    if event is not None:
        subtype = event.raw.get("subtype", "error")
        text = event.raw.get("result", "")
        return f"{subtype}: {text}".strip()[:200]
    return "no result line in stream"


def run_claude(
    prompt: str,
    *,
    allowed_tools: list[str],
    cwd: Path,
    timeout: int = 120,
    claude_bin: str = "claude",
    model: str | None = None,
    on_event: Callable[[StreamEvent], None] | None = None,
) -> RunResult:
    """Invoke the claude CLI and return a parsed RunResult.

    Each parsed stream-json line is passed to ``on_event`` (if given) in order,
    so callers can record the transcript to an event store. ``on_event`` must
    not raise — a raising callback interrupts parsing — so a recording callback
    should absorb its own infrastructure failures (the adapter's recorder does).

    Raises ClaudeCodeSpawnError if the subprocess exits non-zero or the final
    ``result`` line reports ``is_error``.
    """
    cmd = [
        claude_bin,
        "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",  # required alongside -p + stream-json
        "--no-session-persistence",
    ]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
    if model:
        cmd += ["--model", model]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
        )
    except subprocess.TimeoutExpired as exc:
        raise ClaudeCodeSpawnError(-1, f"timed out after {timeout}s") from exc
    except FileNotFoundError as exc:
        raise ClaudeCodeSpawnError(-1, f"claude binary not found: {claude_bin}") from exc

    events: list[StreamEvent] = []
    for event in _parse_stream_lines(proc.stdout):
        events.append(event)
        if on_event is not None:
            on_event(event)
    result = RunResult(returncode=proc.returncode, events=events, stderr=proc.stderr)

    if not result.succeeded:
        raise ClaudeCodeSpawnError(proc.returncode, proc.stderr or _error_summary(result))

    return result
