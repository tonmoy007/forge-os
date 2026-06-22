"""Phase 11 channel use cases (FR-CH-001, FR-CH-002 status, FR-CH-003 broadcast).

The bridge between the ``channel`` CLI and the channel domain. Returns plain
dicts; the channel adapter is injectable for testing and future channels.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_os.channels.base import ChannelAdapter
from forge_os.channels.console import ConsoleChannelAdapter
from forge_os.project.status import (
    next_action_for,
    read_project_status,
    stale_artifact_count,
)


class ChannelUseCases:
    """Channel message normalization, read-only status, and release broadcast."""

    def __init__(self, project_root: Path, channel: ChannelAdapter | None = None) -> None:
        self.project_root = Path(project_root)
        self.channel: ChannelAdapter = channel or ConsoleChannelAdapter()

    def submit_message(self, text: str, sender: str) -> dict[str, Any]:
        """Normalize an inbound channel message into a Forge event (FR-CH-001)."""
        return self.channel.on_message(text, sender).model_dump(mode="json")

    def status_summary(self) -> dict[str, Any]:
        """Return a read-only, fast project status summary (FR-CH-002)."""
        root, _config, state = read_project_status(self.project_root)
        return {
            "project_id": state.project_id,
            "current_stage": state.current_stage_id,
            "next_action": next_action_for(state),
            "stale_artifacts": stale_artifact_count(root),
        }

    def broadcast_release(self, notes: str) -> dict[str, Any]:
        """Push release notes out over the configured channel (FR-CH-003)."""
        self.channel.send_message(notes)
        return {"success": True, "channel": self.channel.channel_id}
