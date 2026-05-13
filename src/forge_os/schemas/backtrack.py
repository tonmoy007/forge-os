from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class BacktrackStatus(StrEnum):
    OPEN = "open"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"

class BacktrackTicket(BaseModel):
    """Schema for tracking rework/backtracking requests."""
    schema_version: str = "0.1.0"
    ticket_id: str
    status: BacktrackStatus = BacktrackStatus.OPEN
    reason: str
    source_stage_id: str
    target_stage_id: str
    affected_artifacts: Sequence[str] = Field(default_factory=list)
    requires_approval: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: str | None = None

class BacktrackStore(BaseModel):
    """Container for persisted backtrack tickets."""
    schema_version: str = "0.1.0"
    tickets: list[BacktrackTicket] = Field(default_factory=list)
