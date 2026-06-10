"""Phase 10 daily digest writer (P10.05, FR-DR-001)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from forge_os.core.state_manager import utc_now
from forge_os.events.log import read_events
from forge_os.events.model import LifecycleEvent

STAGE_TRANSITION_TYPES = ("StageStarted", "StageCompleted", "StageBlocked", "StageOverride")
GATE_TYPES = ("GateStarted", "GateCompleted")
AGENT_ACTOR_TYPES = ("adapter", "agent")


class DailyDigestWriter:
    """Summarize one day of `.forge/events.jsonl` into `pipeline/log/daily-YYYY-MM-DD.md`."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.events_path = self.project_root / ".forge" / "events.jsonl"
        self.log_dir = self.project_root / "pipeline" / "log"

    def write(self, *, for_date: str | None = None, now: str | None = None) -> Path | None:
        """Write the digest for *for_date* (default: today). Returns None when no activity.

        Idempotent: re-running for the same date deterministically overwrites the file.
        """

        digest_date = for_date or (now or utc_now())[:10]
        day_events = [
            event
            for event in read_events(self.events_path)
            if event.timestamp[:10] == digest_date
        ]
        if not day_events:
            return None

        day_events.sort(key=lambda event: (event.timestamp, event.event_id))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        path = self.log_dir / f"daily-{digest_date}.md"
        _ = path.write_text(self._render(digest_date, day_events), encoding="utf-8")
        return path

    def _render(self, digest_date: str, events: list[LifecycleEvent]) -> str:
        lines = [
            f"# Daily Digest — {digest_date}",
            "",
            f"Total events: {len(events)}",
            "",
            "## Events by type",
            "",
        ]
        counts = Counter(event.event_type for event in events)
        lines.extend(f"- {event_type}: {counts[event_type]}" for event_type in sorted(counts))

        transitions = [event for event in events if event.event_type in STAGE_TRANSITION_TYPES]
        if transitions:
            lines.extend(["", "## Stage transitions", ""])
            lines.extend(
                f"- {event.timestamp} `{event.event_type}` stage={event.stage_id or '-'}"
                for event in transitions
            )

        agent_runs = [event for event in events if event.actor.type in AGENT_ACTOR_TYPES]
        if agent_runs:
            lines.extend(["", "## Agent runs", ""])
            for event in agent_runs:
                status = event.payload.get("status", "unknown")
                lines.append(
                    f"- {event.timestamp} `{event.event_type}` "
                    f"adapter={event.actor.id} stage={event.stage_id or '-'} status={status}"
                )

        gate_events = [event for event in events if event.event_type in GATE_TYPES]
        if gate_events:
            lines.extend(["", "## Gate results", ""])
            for event in gate_events:
                detail = ""
                if event.event_type == "GateCompleted":
                    blocking_failed = event.payload.get("blocking_failed", False)
                    result_count = event.payload.get("result_count", 0)
                    detail = f" blocking_failed={blocking_failed} result_count={result_count}"
                lines.append(
                    f"- {event.timestamp} `{event.event_type}` "
                    f"stage={event.stage_id or '-'}{detail}"
                )

        lines.append("")
        return "\n".join(lines)
