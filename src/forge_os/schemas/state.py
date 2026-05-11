"""Phase 01 pipeline state schema."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

StageStatus = Literal["not_started", "active", "blocked", "review_needed", "complete", "skipped"]


class StageState(BaseModel):
    """Per-stage state for the Phase 01 state skeleton."""

    model_config = ConfigDict(extra="allow")

    stage_id: str
    status: StageStatus = "not_started"
    entered_at: str | None = None
    completed_at: str | None = None
    blocked_reason: str | None = None
    artifacts: list[str] = Field(default_factory=list)


class PipelineState(BaseModel):
    """Canonical Phase 01 pipeline state skeleton."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    project_id: str
    profile: str
    current_stage_id: str | None
    stages: list[StageState]
    gates: dict[str, object] = Field(default_factory=dict)
    last_event_id: str | None = None
    created_at: str
    updated_at: str
    metadata: dict[str, object] = Field(default_factory=dict)
