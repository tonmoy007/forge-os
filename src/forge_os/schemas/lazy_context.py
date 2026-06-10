"""Phase 10 lazy context bundle schema (FR-LCB-001..004)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LazyContextBundle(BaseModel):
    """Skill menu + low-confidence lesson index composed within a token cap."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    stage_id: str
    skills_menu: list[dict[str, object]] = Field(default_factory=list)
    lesson_index: list[dict[str, object]] = Field(default_factory=list)
    token_budget: int
    lazy_tokens: int
    trimmed: list[str] = Field(default_factory=list)
    within_budget: bool
