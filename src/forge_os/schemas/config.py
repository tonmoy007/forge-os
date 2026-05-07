"""Phase 01 project configuration schema."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_PROFILES = {"minimal", "standard", "expert"}


class ProjectConfig(BaseModel):
    """Project metadata stored in `.forge/config.yaml`."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    root_policy: str = "project_only"


class SecurityConfig(BaseModel):
    """Phase 01 security configuration skeleton."""

    model_config = ConfigDict(extra="allow")

    profile: str = "baseline"


class HooksConfig(BaseModel):
    """Phase 01 hooks configuration skeleton."""

    model_config = ConfigDict(extra="allow")

    enabled: bool = False


class ForgeConfig(BaseModel):
    """Project configuration for Phase 01 CLI scaffolding."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    project: ProjectConfig
    profile: Literal["minimal", "standard", "expert"] = "minimal"
    default_adapter: str = "dummy"
    adapters: dict[str, dict[str, Any]] = Field(default_factory=dict)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    hooks: HooksConfig = Field(default_factory=HooksConfig)
    features: dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def schema_version_must_be_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("schema_version is required")
        return value

    @field_validator("default_adapter")
    @classmethod
    def default_adapter_must_be_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("default_adapter is required")
        return value
