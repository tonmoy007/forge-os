"""Gate models — criteria, results, and new gate types for Phase 08."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ─── Core gate types ──────────────────────────────────────────────────────────


class GateCriterion(BaseModel):
    """A single gate criterion loaded from pipeline/gates.yaml."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    type: str  # required_file, pattern, external_command, metric_threshold
    stage_id: str | None = None
    severity: str = "blocking"  # blocking, warning, advisory
    enabled: bool = True
    criteria: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int | None = None


class GateFile(BaseModel):
    """Top-level schema for pipeline/gates.yaml."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    gates: list[GateCriterion] = Field(default_factory=list)


class GateResult(BaseModel):
    """Result of evaluating a single gate criterion."""

    model_config = ConfigDict(extra="allow")

    gate_id: str
    stage_id: str | None = None
    status: str  # pass, fail, error, warn, skipped
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: int = 0
    blocking: bool = False
    fix_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─── Phase 08 gate types ─────────────────────────────────────────────────────


class ExternalCommandGate(BaseModel):
    """Gate that executes an external command and checks for success."""

    id: str
    name: str
    command: list[str]
    timeout_seconds: int = 30
    severity: str = "blocking"
    enabled: bool = True


class MetricThresholdGate(BaseModel):
    """Gate that parses a metric from a file and checks a threshold."""

    id: str
    name: str
    metric_file: str
    metric_key: str
    threshold: float
    operator: str = ">="  # >, <, >=, <=, ==
    severity: str = "blocking"
    enabled: bool = True