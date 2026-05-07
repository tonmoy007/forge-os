"""Phase 07 artifact graph and context schemas."""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

ArtifactStatus = Literal["fresh", "stale", "missing"]


class Artifact(BaseModel):
    """One registered project artifact."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: f"artifact-{uuid4()}")
    path: str
    stage_id: str | None = None
    kind: str = "file"
    status: ArtifactStatus = "fresh"
    dependencies: list[str] = Field(default_factory=list)
    dependents: list[str] = Field(default_factory=list)
    content_hash: str | None = None
    modified_at: str | None = None
    token_estimate: int = 0
    registered_at: str
    updated_at: str
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        normalized = value.strip().replace("\\", "/")
        if not normalized:
            raise ValueError("Artifact path is required")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("Artifact path must be project-relative")
        return normalized

    @field_validator("dependencies", "dependents")
    @classmethod
    def normalize_edges(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            candidate = item.strip().replace("\\", "/")
            if candidate and candidate not in normalized:
                normalized.append(candidate)
        return normalized


class ArtifactDocument(BaseModel):
    """Machine-readable artifact registry document."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    artifacts: list[Artifact] = Field(default_factory=list)


class GraphNode(BaseModel):
    """Persisted ADG node."""

    model_config = ConfigDict(extra="allow")

    id: str
    path: str
    stage_id: str | None = None
    status: ArtifactStatus = "fresh"


class GraphEdge(BaseModel):
    """Persisted ADG edge from dependency to dependent."""

    model_config = ConfigDict(extra="allow")

    source: str
    target: str


class ArtifactGraph(BaseModel):
    """Open JSON artifact dependency graph."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class SelectedContextItem(BaseModel):
    """One artifact selected for agent context."""

    model_config = ConfigDict(extra="allow")

    artifact_id: str
    path: str
    priority: int
    token_estimate: int
    reason: str
    content: str


class ContextSelection(BaseModel):
    """Deterministic context pruning result."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    selection_id: str = Field(default_factory=lambda: f"context-{uuid4()}")
    stage_id: str
    token_budget: int
    total_tokens: int
    selected: list[SelectedContextItem] = Field(default_factory=list)
    omitted: list[dict[str, object]] = Field(default_factory=list)
    created_at: str
