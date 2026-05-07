"""Phase 04 gate schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

GateType = Literal["required_file", "pattern"]
GateSeverity = Literal["blocking", "warning", "advisory"]
GateStatus = Literal["pass", "fail", "warn", "skipped", "error"]


class GateCriterion(BaseModel):
    """Loaded gate criterion from `pipeline/gates.yaml`."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    type: GateType
    stage_id: str | None = None
    severity: GateSeverity = "blocking"
    criteria: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int | None = None
    enabled: bool = True


class GateFile(BaseModel):
    """Gate definition file schema."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    gates: list[GateCriterion] = Field(default_factory=list)


class GateResult(BaseModel):
    """Normalized gate evaluation result."""

    schema_version: str = "0.1"
    gate_id: str
    stage_id: str | None = None
    status: GateStatus
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    started_at: str
    finished_at: str
    duration_ms: int
    blocking: bool
    fix_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
