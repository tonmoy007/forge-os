import uuid
from pathlib import Path
from typing import Optional, Sequence

from forge_os.context.registry import ArtifactRegistry
from forge_os.project.backtrack_registry import BacktrackRegistry
from forge_os.schemas.backtrack import BacktrackTicket, BacktrackStatus

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
        target_stage_id: str
    ) -> str:
        ticket_id = f"BT-{uuid.uuid4().hex[:6].upper()}"
        
        # Determine affected artifacts via ADG
        affected_artifacts = self._get_affected_artifacts(target_stage_id)
        
        ticket = BacktrackTicket(
            ticket_id=ticket_id,
            reason=reason,
            source_stage_id=source_stage_id,
            target_stage_id=target_stage_id,
            affected_artifacts=affected_artifacts,
        )
        self.backtrack_registry.create_ticket(ticket)
        return ticket_id

    def _get_affected_artifacts(self, target_stage_id: str) -> Sequence[str]:
        """Find all artifacts produced by the target stage and their downstream dependents."""
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
        
        return sorted(list(affected))

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
        ticket = self.backtrack_registry.update_ticket(
            ticket_id, status=BacktrackStatus.RESOLVED
        )
        return ticket is not None
