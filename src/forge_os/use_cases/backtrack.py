from pathlib import Path
from typing import Optional

from forge_os.project.backtrack_registry import BacktrackRegistry
from forge_os.project.rework_planner import ReworkPlanner
from forge_os.schemas.backtrack import BacktrackTicket


class BacktrackUseCases:
    """Encapsulates business logic for backtrack ticket management."""

    def __init__(self, project_root: Path) -> None:
        self.backtrack_registry = BacktrackRegistry(project_root)
        self.rework_planner = ReworkPlanner(project_root)

    def create_ticket(self, reason: str, source_stage_id: str, target_stage_id: str) -> str:
        return self.rework_planner.create_backtrack_ticket(reason, source_stage_id, target_stage_id)

    def list_tickets(self) -> list[BacktrackTicket]:
        return self.backtrack_registry.list_tickets()

    def get_ticket_plan(self, ticket_id: str) -> Optional[BacktrackTicket]:
        return self.backtrack_registry.get_ticket(ticket_id)

    def approve_ticket(self, ticket_id: str) -> bool:
        return self.rework_planner.approve_ticket(ticket_id)

    def run_rework(self, ticket_id: str) -> bool:
        return self.rework_planner.run_rework(ticket_id)

    def resolve_ticket(self, ticket_id: str) -> bool:
        return self.rework_planner.resolve_ticket(ticket_id)