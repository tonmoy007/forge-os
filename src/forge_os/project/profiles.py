"""Built-in Phase 01 profile templates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StageTemplate:
    """Template for a generated stage definition."""

    id: str
    name: str
    description: str
    order: int
    required_artifacts: tuple[str, ...] = ()
    gate_ids: tuple[str, ...] = ()


MINIMAL_STAGES: tuple[StageTemplate, ...] = (
    StageTemplate(
        "srs",
        "SRS",
        "Define the software requirements.",
        1,
        ("SRS.md",),
        ("srs_exists",),
    ),
    StageTemplate("build", "Build", "Implement the planned solution.", 2, (), ()),
    StageTemplate("deploy", "Deploy", "Prepare and perform deployment.", 3, (), ()),
)

STANDARD_STAGES: tuple[StageTemplate, ...] = (
    StageTemplate(
        "srs",
        "SRS",
        "Define the software requirements.",
        1,
        ("SRS.md",),
        ("srs_exists",),
    ),
    StageTemplate("product", "Product", "Clarify product goals and user value.", 2),
    StageTemplate("architecture", "Architecture", "Decide architecture and major boundaries.", 3),
    StageTemplate("spec", "Spec", "Create implementation specifications.", 4),
    StageTemplate("plan", "Plan", "Create an implementation plan.", 5),
    StageTemplate("build", "Build", "Implement the planned solution.", 6),
    StageTemplate("eval", "Eval", "Evaluate quality and correctness.", 7),
    StageTemplate("deploy", "Deploy", "Prepare and perform deployment.", 8),
    StageTemplate("monitor", "Monitor", "Observe runtime behavior.", 9),
    StageTemplate("feedback", "Feedback", "Collect and analyze feedback.", 10),
    StageTemplate("resolve", "Resolve", "Resolve discovered issues.", 11),
    StageTemplate("release", "Release", "Finalize release artifacts.", 12),
)

EXPERT_STAGES: tuple[StageTemplate, ...] = STANDARD_STAGES


def get_profile_stages(profile: str) -> tuple[StageTemplate, ...]:
    """Return built-in stage templates for a supported profile."""

    if profile == "minimal":
        return MINIMAL_STAGES
    if profile == "standard":
        return STANDARD_STAGES
    if profile == "expert":
        return EXPERT_STAGES
    raise ValueError(f"Unsupported profile: {profile}")


def build_stage_document(profile: str) -> dict[str, object]:
    """Build a serializable `pipeline/stages.yaml` document."""

    stages = get_profile_stages(profile)
    return {
        "schema_version": "0.1",
        "profile": profile,
        "stages": [
            {
                "id": stage.id,
                "name": stage.name,
                "description": stage.description,
                "order": stage.order,
                "required_artifacts": list(stage.required_artifacts),
                "gate_ids": list(stage.gate_ids),
                "allowed_transitions": [stages[index + 1].id] if index + 1 < len(stages) else [],
                "agent_personas": [],
            }
            for index, stage in enumerate(stages)
        ],
    }


def build_gate_document(profile: str) -> dict[str, object]:
    """Build a serializable `pipeline/gates.yaml` document."""

    gates: list[dict[str, object]] = []
    if profile in {"minimal", "standard", "expert"}:
        gates.append(
            {
                "id": "srs_exists",
                "name": "SRS file exists",
                "type": "required_file",
                "stage_id": "srs",
                "severity": "blocking",
                "criteria": {"path": "SRS.md"},
                "timeout_seconds": None,
                "enabled": True,
            }
        )
    return {"schema_version": "0.1", "gates": gates}
