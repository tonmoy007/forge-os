"""Gate definition loading."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from forge_os.gates.models import GateCriterion, GateFile


class GateLoadError(RuntimeError):
    """Raised when gate definitions cannot be loaded or validated."""


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GateLoadError(f"Could not read gate file: {path}") from exc
    except yaml.YAMLError as exc:
        raise GateLoadError(f"Gate file is not valid YAML: {path}") from exc

    if raw is None:
        return {"schema_version": "0.1", "gates": []}
    if not isinstance(raw, dict):
        raise GateLoadError(f"Gate file must contain a YAML mapping: {path}")
    return raw


def load_gate_file(path: Path) -> list[GateCriterion]:
    """Load and validate gate criteria from `pipeline/gates.yaml`."""

    raw = _read_yaml_mapping(path)
    try:
        return GateFile.model_validate(raw).gates
    except ValidationError as exc:
        raise GateLoadError(str(exc)) from exc
