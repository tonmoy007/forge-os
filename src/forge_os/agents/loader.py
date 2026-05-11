"""Load built-in and project-local Phase 05 agent definitions."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from forge_os.agents.models import AgentDefinition, OutputContract


class AgentLoadError(RuntimeError):
    """Raised when agent personas or output contracts cannot be loaded."""


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AgentLoadError(f"Could not read agent document: {path}") from exc
    except yaml.YAMLError as exc:
        raise AgentLoadError(f"Agent document is not valid YAML: {path}") from exc

    if not isinstance(raw, dict):
        raise AgentLoadError(f"Agent document must contain a YAML mapping: {path}")
    return raw


def _builtin_yaml(package: str, name: str) -> dict[str, Any]:
    try:
        text = resources.files(package).joinpath(name).read_text(encoding="utf-8")
        raw = yaml.safe_load(text)
    except (FileNotFoundError, ModuleNotFoundError, yaml.YAMLError) as exc:
        raise AgentLoadError(f"Could not load built-in agent document: {name}") from exc

    if not isinstance(raw, dict):
        raise AgentLoadError(f"Built-in agent document must contain a mapping: {name}")
    return raw


def _agent_from_mapping(raw: dict[str, Any], *, source: str) -> AgentDefinition:
    try:
        return AgentDefinition.model_validate(raw)
    except ValidationError as exc:
        raise AgentLoadError(f"Invalid agent persona in {source}: {exc}") from exc


def _contract_from_mapping(raw: dict[str, Any], *, source: str) -> OutputContract:
    try:
        return OutputContract.model_validate(raw)
    except ValidationError as exc:
        raise AgentLoadError(f"Invalid output contract in {source}: {exc}") from exc


def load_personas(project_root: Path) -> dict[str, AgentDefinition]:
    """Load personas from project-local overrides plus bundled defaults."""

    personas: dict[str, AgentDefinition] = {}
    package = "forge_os.agents.personas"
    for resource in resources.files(package).iterdir():
        if resource.name.endswith((".yaml", ".yml")):
            persona = _agent_from_mapping(
                _builtin_yaml(package, resource.name),
                source=resource.name,
            )
            personas[persona.id] = persona

    local_dir = project_root / ".forge" / "agents" / "personas"
    if local_dir.exists():
        for path in sorted(local_dir.glob("*.yaml")):
            persona = _agent_from_mapping(_read_yaml(path), source=str(path))
            personas[persona.id] = persona
    return personas


def load_contracts(project_root: Path) -> dict[str, OutputContract]:
    """Load output contracts from project-local overrides plus bundled defaults."""

    contracts: dict[str, OutputContract] = {}
    package = "forge_os.agents.contracts"
    for resource in resources.files(package).iterdir():
        if resource.name.endswith((".yaml", ".yml")):
            contract = _contract_from_mapping(
                _builtin_yaml(package, resource.name),
                source=resource.name,
            )
            contracts[contract.id] = contract

    local_dir = project_root / ".forge" / "agents" / "contracts"
    if local_dir.exists():
        for path in sorted(local_dir.glob("*.yaml")):
            contract = _contract_from_mapping(_read_yaml(path), source=str(path))
            contracts[contract.id] = contract
    return contracts


def persona_for_stage(project_root: Path, stage_id: str) -> AgentDefinition:
    """Return the first configured stage persona for a stage id."""

    personas = load_personas(project_root)
    for persona in sorted(personas.values(), key=lambda item: item.id):
        if persona.category == "stage" and stage_id in persona.stage_ids:
            return persona
    raise AgentLoadError(f"No stage persona configured for stage `{stage_id}`.")


def contract_for_persona(project_root: Path, persona: AgentDefinition) -> OutputContract:
    """Return the output contract declared by a persona."""

    if persona.output_contract_id is None:
        raise AgentLoadError(f"Persona `{persona.id}` does not declare an output contract.")
    contracts = load_contracts(project_root)
    contract = contracts.get(persona.output_contract_id)
    if contract is None:
        raise AgentLoadError(
            f"Output contract `{persona.output_contract_id}` for persona "
            f"`{persona.id}` was not found."
        )
    return contract
