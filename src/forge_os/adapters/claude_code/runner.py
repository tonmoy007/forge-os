"""Claude Code CLI subprocess invocation and stream-json line parser."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ClaudeCodeSpawnError(RuntimeError):
    """Raised when the claude subprocess exits with a non-zero code."""

    def __init__(self, returncode: int, stderr: str) -> None:
        super().__init__(f"claude exited {returncode}: {stderr.strip()[:200]}")
        self.returncode = returncode
        self.stderr = stderr


@dataclass
class StreamEvent:
    """One parsed stream-json line from the claude CLI."""

    type: str
    raw: dict[str, Any]

    # Convenience accessors
    @property
    def content(self) -> str:
        return self.raw.get("content", "")

    @property
    def tool_name(self) -> str:
        return self.raw.get("name", "")

    @property
    def tool_input(self) -> dict[str, Any]:
        return self.raw.get("input", {})

    @property
    def error_message(self) -> str:
        err = self.raw.get("error", {})
        return err.get("message", "") if isinstance(err, dict) else str(err)


@dataclass
class RunResult:
    """Aggregated result of a claude subprocess run."""

    returncode: int
    events: list[StreamEvent] = field(default_factory=list)
    stderr: str = ""

    @property
    def text_output(self) -> str:
        return "\n".join(e.content for e in self.events if e.type == "text" and e.content)

    @property
    def tool_uses(self) -> list[StreamEvent]:
        return [e for e in self.events if e.type == "tool_use"]

    @property
    def errors(self) -> list[StreamEvent]:
        return [e for e in self.events if e.type == "error"]

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.errors


def _parse_stream_lines(stdout: str) -> Iterator[StreamEvent]:
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = obj.get("type", "unknown")
        yield StreamEvent(type=event_type, raw=obj)


def run_claude(
    prompt: str,
    *,
    allowed_tools: list[str],
    cwd: Path,
    max_turns: int = 10,
    timeout: int = 120,
    claude_bin: str = "claude",
    on_event: Callable[[StreamEvent], None] | None = None,
) -> RunResult:
    """Invoke the claude CLI and return a parsed RunResult.

    Each parsed stream-json line is passed to ``on_event`` (if given) in order,
    so callers can record the transcript to an event store. ``on_event`` fires
    for every line — including those of a run that ultimately fails — before
    this function raises. ``on_event`` must not raise: an exception from it
    propagates and interrupts parsing, so a recording callback should absorb its
    own infrastructure failures (the adapter's recorder does).

    Raises ClaudeCodeSpawnError if the subprocess exits non-zero.
    """
    cmd = [
        claude_bin,
        "-p", prompt,
        "--output-format", "stream-json",
        "--no-session-persistence",
        "--max-turns", str(max_turns),
    ]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]

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
        raise ClaudeCodeSpawnError(proc.returncode, proc.stderr)

    return result
