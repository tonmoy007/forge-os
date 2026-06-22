"""Channel feedback intake queue for Stage 10 triage (FR-CH-002, P11.05).

Append-only JSONL under ``.forge/channels/feedback.jsonl`` with deduplication and
per-sender rate limiting (P11.07). ``forge_dir``-injected; never writes canonical
pipeline state.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from forge_os.channels.errors import ChannelDuplicateError, ChannelRateLimitError
from forge_os.schemas.channel import FeedbackItem

FEEDBACK_RELPATH = Path(".forge") / "channels" / "feedback.jsonl"


class FeedbackQueue:
    """Persistent queue of channel feedback awaiting Stage 10 triage."""

    def __init__(
        self,
        project_root: Path,
        *,
        max_per_window: int = 5,
        window_seconds: float = 60.0,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.path = self.project_root / FEEDBACK_RELPATH
        self.max_per_window = max_per_window
        self.window_seconds = window_seconds

    def list_pending(self) -> list[FeedbackItem]:
        """Return all pending feedback items (empty if none)."""
        if not self.path.exists():
            return []
        items = [
            FeedbackItem.model_validate_json(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return [item for item in items if item.status == "pending"]

    def submit(self, item: FeedbackItem, *, now: datetime | None = None) -> FeedbackItem:
        """Enqueue *item*, rejecting duplicates and rate-limit violations.

        Dedup: identical (sender, text) already pending. Rate limit: more than
        ``max_per_window`` pending items from the sender within ``window_seconds``.
        """
        moment = now or datetime.now()
        existing = self.list_pending()

        if any(e.sender == item.sender and e.text == item.text for e in existing):
            raise ChannelDuplicateError(f"duplicate feedback from '{item.sender}'")

        recent = [
            e
            for e in existing
            if e.sender == item.sender and self._within_window(e.created_at, moment)
        ]
        if len(recent) >= self.max_per_window:
            raise ChannelRateLimitError(
                f"sender '{item.sender}' exceeded "
                f"{self.max_per_window} items per {self.window_seconds:.0f}s"
            )

        self._append(item)
        return item

    def _within_window(self, created_at: str, moment: datetime) -> bool:
        try:
            created = datetime.fromisoformat(created_at)
            return (moment - created).total_seconds() < self.window_seconds
        except (ValueError, TypeError):
            # Malformed, or a naive/aware mismatch in the subtraction — treat as
            # outside the window rather than crashing feedback intake.
            return False

    def _append(self, item: FeedbackItem) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as out:
            out.write(item.model_dump_json() + "\n")
