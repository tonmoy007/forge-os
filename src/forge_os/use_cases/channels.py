"""Phase 11 channel use cases (FR-CH-001, FR-CH-002 status, FR-CH-003 broadcast).

The bridge between the ``channel`` CLI and the channel domain. Returns plain
dicts; the channel adapter is injectable for testing and future channels.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_os.channels.base import ChannelAdapter
from forge_os.channels.console import ConsoleChannelAdapter
from forge_os.channels.errors import ChannelError
from forge_os.channels.identity import ChannelIdentityStore
from forge_os.channels.intake import FeedbackQueue
from forge_os.channels.policy import authorize_channel_action
from forge_os.project.security_audit import SecurityAuditLog
from forge_os.project.security_enforcer import SecurityEnforcer
from forge_os.project.status import (
    next_action_for,
    read_project_status,
    stale_artifact_count,
)
from forge_os.schemas.channel import FeedbackItem
from forge_os.schemas.security import SecurityProfile


class ChannelUseCases:
    """Channel message normalization, read-only status, and release broadcast."""

    def __init__(self, project_root: Path, channel: ChannelAdapter | None = None) -> None:
        self.project_root = Path(project_root)
        self.channel: ChannelAdapter = channel or ConsoleChannelAdapter()
        self.identities = ChannelIdentityStore(self.project_root)
        self.feedback = FeedbackQueue(self.project_root)
        self.audit_log = SecurityAuditLog(self.project_root)
        # Default profile denies all capabilities (fail-closed) — the same pattern
        # as ExtensionUseCases/SecurityUseCases. Loading the project profile is a follow-up.
        self.enforcer = SecurityEnforcer(
            self.project_root, SecurityProfile(profile_id="default"), self.audit_log
        )

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

    def submit_feedback(self, text: str, sender: str) -> dict[str, Any]:
        """Queue channel feedback for Stage 10 triage (FR-CH-002, P11.05).

        Feedback is permitted for unbound senders (FR-CH-005); the queue enforces
        dedup + rate-limit (P11.07).
        """
        channel_id = self.channel.channel_id
        identity = self.identities.get(channel_id, sender)
        try:
            authorize_channel_action("feedback", identity, self.enforcer)
            item = self.feedback.submit(
                FeedbackItem(channel_id=channel_id, sender=sender, text=text)
            )
        except ChannelError as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "feedback_id": item.feedback_id}

    def request_pairing(self, sender: str) -> dict[str, Any]:
        """Begin identity binding: return a one-time pairing code (FR-CH-005)."""
        try:
            code = self.identities.begin_pairing(self.channel.channel_id, sender)
        except ChannelError as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "pairing_code": code}

    def confirm_pairing(
        self, sender: str, pairing_code: str, forge_identity: str
    ) -> dict[str, Any]:
        """HITL-confirm a pairing, binding the sender to a Forge identity (FR-CH-005)."""
        bound = self.identities.confirm(
            self.channel.channel_id, sender, pairing_code, forge_identity
        )
        if not bound:
            return {"success": False, "error": "invalid pairing code"}
        return {"success": True, "sender": sender, "forge_identity": forge_identity}
