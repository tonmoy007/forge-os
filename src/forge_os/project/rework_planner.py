import uuid
from collections.abc import Sequence
from pathlib import Path

from forge_os.context.registry import ArtifactRegistry
from forge_os.project.backtrack_registry import BacktrackRegistry
from forge_os.schemas.backtrack import BacktrackStatus, BacktrackTicket


class ReworkPlanner:
    """Generates rework plans based on ADG cascades."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.artifact_registry = ArtifactRegistry(project_root)
        self.backtrack_registry = BacktrackRegistry(project_root)

    def create_backtrack_ticket(
        self,
        reason: str,
        source_stage_id: str,
        target_stage_id: str,
    ) -> str:
        ticket_id = f"BT-{uuid.uuid4().hex[:6].upper()}"

        # Determine affected artifacts and downstream stages via ADG
        affected_artifacts, downstream_stages = self._get_affected_artifacts(
            target_stage_id
        )

        ticket = BacktrackTicket(
            ticket_id=ticket_id,
            reason=reason,
            source_stage_id=source_stage_id,
            target_stage_id=target_stage_id,
            affected_artifacts=affected_artifacts,
        )
        self.backtrack_registry.create_ticket(ticket)
        return ticket_id

    def get_downstream_stages(self, target_stage_id: str) -> list[str]:
        """Return stage IDs affected by changes to the target stage's artifacts."""
        _, downstream_stages = self._get_affected_artifacts(target_stage_id)
        return downstream_stages

    def _get_affected_artifacts(
        self, target_stage_id: str
    ) -> tuple[Sequence[str], list[str]]:
        """Find all artifacts affected by the target stage and their downstream.

        Returns (sorted affected artifact paths, sorted downstream stage IDs).
        """
        document = self.artifact_registry.load()

        # 1. Start with artifacts from the target stage
        seeds = [a.path for a in document.artifacts if a.stage_id == target_stage_id]

        # 2. Traverse downstream in ADG
        affected = set(seeds)
        queue = list(seeds)

        while queue:
            current = queue.pop(0)
            artifact = next((a for a in document.artifacts if a.path == current), None)
            if artifact:
                for dependent in artifact.dependents:
                    if dependent not in affected:
                        affected.add(dependent)
                        queue.append(dependent)

        # 3. Collect downstream stage IDs from affected artifacts
        affected_paths = sorted(affected)
        downstream_stages = sorted(
            {
                a.stage_id
                for a in document.artifacts
                if a.path in affected and a.stage_id is not None and a.stage_id != target_stage_id
            }
        )
        return affected_paths, downstream_stages

    def approve_ticket(self, ticket_id: str) -> bool:
        ticket = self.backtrack_registry.update_ticket(
            ticket_id, status=BacktrackStatus.APPROVED
        )
        return ticket is not None

    def run_rework(self, ticket_id: str) -> bool:
        """
        Marks affected artifacts as stale and prepares stages for rerun.
        In a real implementation, this would integrate with the state machine
        to set a 'diff-mode' flag on the target stage.
        """
        ticket = self.backtrack_registry.get_ticket(ticket_id)
        if not ticket or ticket.status != BacktrackStatus.APPROVED:
            return False
        
        # Mark artifacts as stale in the registry
        document = self.artifact_registry.load()
        for path in ticket.affected_artifacts:
            artifact = next((a for a in document.artifacts if a.path == path), None)
            if artifact:
                artifact.status = "stale"
        
        self.artifact_registry.save(document)
        self.backtrack_registry.update_ticket(ticket_id, status=BacktrackStatus.IN_PROGRESS)
        return True

    def resolve_ticket(self, ticket_id: str) -> bool:
        """Resolve a ticket and clear stale flags on affected artifacts."""
        ticket = self.backtrack_registry.get_ticket(ticket_id)
        if not ticket:
            return False

        # Clear stale flags on artifacts owned by this ticket
        if ticket.affected_artifacts:
            document = self.artifact_registry.load()
            changed = False
            for artifact in document.artifacts:
                if artifact.path in ticket.affected_artifacts and artifact.status == "stale":
                    artifact.status = "fresh"
                    artifact.updated_at = utc_now()
                    changed = True
            # Also clear downstream propagation: any artifact whose stale
            # status traces through one of our artifacts gets refreshed.
            if changed:
                self.artifact_registry.save(document)

        result = self.backtrack_registry.update_ticket(
            ticket_id, status=BacktrackStatus.RESOLVED
        )
        return result is not None


def utc_now() -> str:
    """RFC 3339 UTC timestamp for artifact metadata."""
    from datetime import UTC, datetime
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
