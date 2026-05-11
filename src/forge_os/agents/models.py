"""Phase 05 agent persona and output contract models."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AgentCategory = Literal["stage", "cross_stage"]
ContractRequirementType = Literal["file_exists"]


class OutputArtifact(BaseModel):
    """A normalized artifact produced by an agent run."""

    model_config = ConfigDict(extra="allow")

    path: str
    kind: str = "file"
    description: str | None = None


class AgentDefinition(BaseModel):
    """Portable persona definition supplied to kernel adapters."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    id: str
    name: str
    category: AgentCategory
    role: str
    prompt: str
    stage_ids: list[str] = Field(default_factory=list)
    default_tools: list[str] = Field(default_factory=list)
    output_contract_id: str | None = None


class ContractRequirement(BaseModel):
    """One deterministic output requirement."""

    model_config = ConfigDict(extra="allow")

    id: str
    type: ContractRequirementType = "file_exists"
    path: str
    description: str | None = None
    blocking: bool = True


class OutputContract(BaseModel):
    """Deterministic contract checked after an adapter stops."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    id: str
    stage_id: str
    persona_id: str
    required_outputs: list[ContractRequirement] = Field(default_factory=list)


class ContractCheck(BaseModel):
    """Result for one output contract requirement."""

    model_config = ConfigDict(extra="allow")

    requirement_id: str
    passed: bool
    blocking: bool
    summary: str


class ContractValidationResult(BaseModel):
    """Normalized output contract validation result."""

    model_config = ConfigDict(extra="allow")

    contract_id: str
    stage_id: str
    passed: bool
    checks: list[ContractCheck] = Field(default_factory=list)


class AgentRunRecord(BaseModel):
    """Record persisted to `.forge/agent-runs.jsonl`."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    run_id: str
    adapter: str
    handle_id: str
    persona_id: str
    stage_id: str
    status: str
    started_at: str
    completed_at: str | None = None
    outputs: list[OutputArtifact] = Field(default_factory=list)
    contract: ContractValidationResult | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def validate_contract(project_root: Path, contract: OutputContract) -> ContractValidationResult:
    """Validate a contract using deterministic local checks."""

    checks: list[ContractCheck] = []
    for requirement in contract.required_outputs:
        artifact_path = project_root / requirement.path
        passed = artifact_path.exists() if requirement.type == "file_exists" else False
        if passed:
            summary = f"Required output exists: {requirement.path}"
        else:
            summary = f"Required output is missing: {requirement.path}"
        checks.append(
            ContractCheck(
                requirement_id=requirement.id,
                passed=passed,
                blocking=requirement.blocking,
                summary=summary,
            )
        )

    blocking_failures = [check for check in checks if check.blocking and not check.passed]
    return ContractValidationResult(
        contract_id=contract.id,
        stage_id=contract.stage_id,
        passed=not blocking_failures,
        checks=checks,
    )
