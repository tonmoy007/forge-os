"""ClaudeCodeAdapter — real kernel adapter over the claude CLI."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any
from uuid import uuid4

from forge_os.adapters.base import AgentHandle, BaseKernelAdapter, ToolList
from forge_os.adapters.claude_code.hooks import ClaudeSettingsHookWriter
from forge_os.adapters.claude_code.runner import (
    ClaudeCodeSpawnError,
    RunResult,
    StreamEvent,
    run_claude,
    validate_permission_mode,
)
from forge_os.adapters.claude_code.tool_map import DEFAULT_ABSTRACT_TOOLS, to_claude_tools
from forge_os.agents.models import AgentDefinition, OutputArtifact
from forge_os.events.store import EventStore
from forge_os.project.security_enforcer import SecurityEnforcer
from forge_os.schemas.security import SecurityDecision

log = logging.getLogger("forge.kernel.claude_code")

# Event Store event types recorded by this adapter — the determinism boundary
# (ADR-005 / FR-ES-001). Names follow the PascalCase convention used for
# EventStore event types (cf. events/model.py EventType, e.g. "StateSaved").
EVENT_SPAWN_STARTED = "AdapterSpawnStarted"
EVENT_STREAM = "AdapterStreamEvent"
EVENT_SPAWN_COMPLETED = "AdapterSpawnCompleted"
EVENT_SPAWN_FAILED = "AdapterSpawnFailed"


class ClaudeCodeAdapter(BaseKernelAdapter):
    """Kernel adapter that drives Claude Code via subprocess + stream-json.

    Slice 1: subprocess invocation and stream-json parsing.
    Slice 2: event-store recording (every stream-json line + spawn lifecycle is
        appended under a per-spawn ``run_id`` stream) and `.claude/settings.json`
        hook lifecycle.
    Slice 3 (planned): replay from event store.

    When ``event_store`` is injected, each spawn records an ``AdapterSpawnStarted``
    event, one ``AdapterStreamEvent`` per stream-json line, then either an
    ``AdapterSpawnCompleted`` or ``AdapterSpawnFailed`` event. The ``run_id`` that
    groups these events is exposed on ``AgentHandle.metadata["run_id"]``.

    When ``hook_command`` is set, the adapter installs PreToolUse/PostToolUse
    hooks into `.claude/settings.json` for the duration of the spawn and tears
    them down afterwards (even if the spawn fails).

    When ``security_enforcer`` is injected (Slice 5), every spawn is validated
    against the project security profile *before* the subprocess starts
    (action ``execute_command``, capability ``shell``). A DENIED decision
    blocks the spawn with ClaudeCodeSpawnError. The gate is fail-closed: if
    the enforcer itself raises (e.g. the audit log is unwritable), the spawn
    aborts with that error — never proceeding unaudited. Audit authority is
    split by concern: `.forge/security-audit.jsonl` (written by the enforcer)
    is authoritative for security decisions; the event store records only the
    spawn lifecycle. Default ``None`` means no gate.
    """

    adapter_id = "claude-code"
    optional_capabilities = frozenset({"stream", "hook_events", "replay"})

    def __init__(
        self,
        project_root: Path | str,
        *,
        claude_bin: str = "claude",
        timeout: int = 120,
        model: str | None = None,
        permission_mode: str | None = None,
        event_store: EventStore | None = None,
        hook_command: str | None = None,
        security_enforcer: SecurityEnforcer | None = None,
    ) -> None:
        validate_permission_mode(permission_mode)
        self.project_root = Path(project_root)
        self.claude_bin = claude_bin
        self.timeout = timeout
        self.model = model
        self.permission_mode = permission_mode
        self._event_store = event_store
        self.hook_command = hook_command
        self._security_enforcer = security_enforcer

    def get_default_tools(self) -> ToolList:
        return list(DEFAULT_ABSTRACT_TOOLS)

    def spawn_agent(
        self,
        persona: AgentDefinition,
        context: str,
        tools: ToolList,
    ) -> AgentHandle:
        """Invoke claude CLI and return a completed AgentHandle.

        Records the spawn lifecycle to the event store (when one is injected)
        and manages the `.claude/settings.json` hook lifecycle (when a
        ``hook_command`` is configured). Raises ClaudeCodeSpawnError on
        security denial, non-zero exit, or parse errors, or ClaudeSettingsError
        if hook-config install fails; either way a terminal
        ``AdapterSpawnFailed`` event is recorded first.
        """
        granted_abstract = self._intersect_tools(tools)
        claude_tools = to_claude_tools(granted_abstract)
        prompt = self._build_prompt(persona, context)
        run_id = _new_run_id()

        self._record_spawn_started(
            run_id, persona, context, prompt, granted_abstract, claude_tools
        )

        try:
            self._enforce_spawn_allowed(persona)
            with self._hook_context():
                result = run_claude(
                    prompt,
                    allowed_tools=claude_tools,
                    cwd=self.project_root,
                    timeout=self.timeout,
                    claude_bin=self.claude_bin,
                    model=self.model,
                    permission_mode=self.permission_mode,
                    on_event=self._stream_recorder(run_id),
                )
        except Exception as exc:
            # Any spawn-path failure (subprocess error, or hook-config
            # install/teardown error) records a terminal event and re-raises the
            # ORIGINAL error unchanged — recording must never mask it, and the
            # event stream must not be left without a terminal event.
            self._record_spawn_failed(run_id, exc)
            raise

        handle = self._build_handle(persona, granted_abstract, result, run_id)
        self._record_spawn_completed(run_id, handle, result)
        return handle

    def replay_session(self, run_id: str) -> AgentHandle:
        """Reconstruct a past spawn's AgentHandle from the event store (FR-ES-003).

        Re-projects the recorded event stream for ``run_id`` without invoking the
        subprocess — the same run_id yields the same handle every time (ADR-005).
        Raises ReplayError if no event store is configured, or the run is
        missing, incomplete, or failed.
        """
        # Lazy import: replay imports projection helpers from this module, so a
        # top-level import here would create a cycle.
        from forge_os.adapters.claude_code.replay import ReplayError
        from forge_os.adapters.claude_code.replay import replay_session as _replay

        if self._event_store is None:
            raise ReplayError("no event store configured for replay")
        return _replay(self._event_store, run_id)

    def _enforce_spawn_allowed(self, persona: AgentDefinition) -> None:
        """Security gate before the subprocess spawns (P055.13).

        Asks the enforcer to validate executing the claude binary under the
        ``shell`` capability — the same action/capability pair used by
        SecurityEnforcer.run_command, so one capability rule governs both
        paths. The enforcer audits every decision; only DENIED blocks
        (WARNED/prompt falls through, matching run_command semantics).

        Fail-closed: an exception from the enforcer (audit-log I/O error,
        enforcer bug) propagates and aborts the spawn — distinguishable from
        a denial, which always raises ClaudeCodeSpawnError. The caller-facing
        failure boundary in spawn_agent records the terminal event either way.
        """
        if self._security_enforcer is None:
            return
        decision = self._security_enforcer.validate_action(
            {"type": "kernel_adapter", "adapter_id": self.adapter_id},
            "execute_command",
            target=self.claude_bin,
            capability="shell",
        )
        if decision == SecurityDecision.DENIED:
            raise ClaudeCodeSpawnError(
                -1,
                f"security profile denied executing `{self.claude_bin}` "
                f"(capability=shell) for persona {persona.id}",
            )

    def _build_prompt(self, persona: AgentDefinition, context: str) -> str:
        parts = [f"Role: {persona.role}", f"\n{persona.prompt}"]
        if context:
            parts.append(f"\n\nContext:\n{context}")
        return "\n".join(parts)

    def _hook_context(self) -> AbstractContextManager[Any]:
        """Hook-config lifecycle for the spawn, or a no-op when disabled."""
        if self.hook_command is None:
            return nullcontext()
        return ClaudeSettingsHookWriter(
            self.project_root,
            pre_tool_command=self.hook_command,
            post_tool_command=self.hook_command,
        )

    def _build_handle(
        self,
        persona: AgentDefinition,
        granted_tools: list[str],
        result: RunResult,
        run_id: str,
    ) -> AgentHandle:
        return AgentHandle(
            provider=self.adapter_id,
            persona_id=persona.id,
            stage_id=persona.stage_ids[0] if persona.stage_ids else None,
            status="completed",
            outputs=extract_text_outputs(result),
            metadata=self._build_metadata(persona, granted_tools, result, run_id),
        )

    def _build_metadata(
        self,
        persona: AgentDefinition,
        granted_tools: list[str],
        result: RunResult,
        run_id: str,
    ) -> dict[str, Any]:
        return {
            "adapter": self.adapter_id,
            "run_id": run_id,
            "tools_granted": granted_tools,
            "tool_use_count": len(result.tool_uses),
            "event_count": len(result.events),
            "text_length": len(result.text_output),
            "returncode": result.returncode,
            "usage": result.usage,
            "total_cost_usd": result.total_cost_usd,
        }

    # ── Event-store recording (FR-ES-001 / ADR-005) ─────────────────────────
    #
    # Recording is an audit side-channel: a write failure must never abort or
    # mask the actual spawn (mirrors StateManager's best-effort Event Store
    # dual-write). `_safe_append` swallows store errors but logs them with
    # context, so observability is preserved without silent failure.

    def _safe_append(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_store is None:
            return
        try:
            self._event_store.append(run_id, event_type, payload)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "event-store append failed (run_id=%s, type=%s): %s",
                run_id,
                event_type,
                exc,
            )

    def _stream_recorder(
        self, run_id: str
    ) -> Callable[[StreamEvent], None] | None:
        """Build a per-line recorder, or None when no event store is wired."""
        if self._event_store is None:
            return None

        def _record(event: StreamEvent) -> None:
            self._safe_append(run_id, EVENT_STREAM, {"type": event.type, "raw": event.raw})

        return _record

    def _record_spawn_started(
        self,
        run_id: str,
        persona: AgentDefinition,
        context: str,
        prompt: str,
        granted_tools: list[str],
        claude_tools: list[str],
    ) -> None:
        self._safe_append(
            run_id,
            EVENT_SPAWN_STARTED,
            {
                "adapter": self.adapter_id,
                "persona_id": persona.id,
                "role": persona.role,
                "stage_id": persona.stage_ids[0] if persona.stage_ids else None,
                "prompt": prompt,
                "context": context,
                "granted_tools": granted_tools,
                "claude_tools": claude_tools,
            },
        )

    def _record_spawn_completed(
        self, run_id: str, handle: AgentHandle, result: RunResult
    ) -> None:
        self._safe_append(
            run_id,
            EVENT_SPAWN_COMPLETED,
            {
                "adapter": self.adapter_id,
                "handle_id": handle.handle_id,
                "status": handle.status,
                "returncode": result.returncode,
                "tool_use_count": len(result.tool_uses),
                "text_length": len(result.text_output),
                "metadata": handle.metadata,
            },
        )

    def _record_spawn_failed(self, run_id: str, exc: BaseException) -> None:
        self._safe_append(
            run_id,
            EVENT_SPAWN_FAILED,
            {
                "adapter": self.adapter_id,
                "returncode": getattr(exc, "returncode", -1),
                "error": str(exc),
            },
        )


def extract_text_outputs(result: RunResult) -> list[OutputArtifact]:
    """Project a run's text transcript into output artifacts.

    Shared by live spawn (`_build_handle`) and replay so both derive outputs
    identically from a RunResult.
    """
    text = result.text_output
    if not text:
        return []
    return [OutputArtifact(path="", kind="text", description=text[:500])]


def _new_run_id() -> str:
    """Unique identifier for one spawn, used as the event-store stream id."""
    return f"ccrun-{uuid4().hex}"
