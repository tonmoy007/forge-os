"""Phase 06 memory schemas."""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

LessonStatus = Literal["pending", "approved", "deprecated"]
LessonSource = Literal["manual", "inferred", "reflection"]


class Lesson(BaseModel):
    """A durable project-level lesson stored in `.forge/lessons.yaml`."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: f"lesson-{uuid4()}")
    text: str = Field(min_length=1)
    status: LessonStatus = "pending"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    stage_id: str | None = None
    source: LessonSource = "manual"
    created_at: str
    updated_at: str
    approved_at: str | None = None
    deprecated_at: str | None = None
    last_used_at: str | None = None
    use_count: int = 0
    dormant: bool = False
    dormant_at: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Lesson text is required")
        return stripped

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for tag in value:
            candidate = tag.strip().lower()
            if candidate and candidate not in normalized:
                normalized.append(candidate)
        return normalized


class LessonDocument(BaseModel):
    """Human-readable lesson store document."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    lessons: list[Lesson] = Field(default_factory=list)


class Reflection(BaseModel):
    """A structured reflection captured after lifecycle activity."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: f"reflection-{uuid4()}")
    stage_id: str | None = None
    event_type: str
    summary: str = Field(min_length=1)
    observations: list[str] = Field(default_factory=list)
    lesson_ids: list[str] = Field(default_factory=list)
    created_at: str
    metadata: dict[str, object] = Field(default_factory=dict)


class ReflectionDocument(BaseModel):
    """One reflection file stored under `.forge/reflections/`."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    reflection: Reflection
