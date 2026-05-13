import json
from pathlib import Path

from forge_os.schemas.backtrack import BacktrackStore, BacktrackTicket


class BacktrackRegistry:
    """Manage `.forge/backtrack.json`."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.store_path = self.project_root / ".forge" / "backtrack.json"

    def load(self) -> BacktrackStore:
        if not self.store_path.exists():
            return BacktrackStore()
        try:
            raw = json.loads(self.store_path.read_text(encoding="utf-8"))
            return BacktrackStore.model_validate(raw)
        except Exception:
            return BacktrackStore()

    def save(self, store: BacktrackStore) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(
            json.dumps(store.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    def create_ticket(self, ticket: BacktrackTicket) -> None:
        store = self.load()
        store.tickets.append(ticket)
        self.save(store)

    def update_ticket(self, ticket_id: str, **updates) -> BacktrackTicket | None:
        store = self.load()
        for ticket in store.tickets:
            if ticket.ticket_id == ticket_id:
                for key, value in updates.items():
                    setattr(ticket, key, value)
                self.save(store)
                return ticket
        return None

    def get_ticket(self, ticket_id: str) -> BacktrackTicket | None:
        store = self.load()
        for ticket in store.tickets:
            if ticket.ticket_id == ticket_id:
                return ticket
        return None

    def list_tickets(self) -> list[BacktrackTicket]:
        return self.load().tickets
