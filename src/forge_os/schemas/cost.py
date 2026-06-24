"""Schemas for `forge cost` — recorded spawn token/$ aggregation.

FR-TE-001 (token cost stored in event metadata), FR-TE-004 (production vs
evolution spend), FR-COST-002 (`forge cost` surface). Pure pydantic — no
forge_os imports.
"""

from pydantic import BaseModel, Field


class StageCost(BaseModel):
    """Aggregated token/$ spend for one stage's recorded spawns."""

    stage_id: str
    spawns: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    # None means no spawn in this stage carried kernel pricing (e.g. an adapter
    # without a price model) — reported as "no pricing", never faked to 0.
    cost_usd: float | None = None


class CostReport(BaseModel):
    """Production token/$ spend, grouped by stage, from recorded spawn events."""

    stages: list[StageCost] = Field(default_factory=list)
    # Adapters that actually produced cost events (production data = claude_code).
    adapters: list[str] = Field(default_factory=list)
    production_spawns: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float | None = None
    # Shadow/canary and Dreamer/Skill-Miner streams have no data source in code
    # today (FR-TE-004). Reported honestly rather than fabricated as 0.
    evolution_note: str = "no data source yet — shadow/canary spend is not wired"
    exploration_note: str = "no data source yet — Dreamer/Skill-Miner do not spawn agents"
