"""Configuration loading and validation helpers."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from forge_os.project.detect import find_project_root
from forge_os.schemas.config import ForgeConfig


class ConfigError(RuntimeError):
    """Raised when Forge configuration cannot be loaded or validated."""


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Could not read config file: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Config file is not valid YAML: {path}") from exc

    if raw is None:
        raise ConfigError(f"Config file is empty: {path}")
    if not isinstance(raw, dict):
        raise ConfigError(f"Config file must contain a YAML mapping: {path}")
    return raw


def load_config(path: Path) -> ForgeConfig:
    """Load and validate a Forge config file."""

    raw = _read_yaml_mapping(path)
    try:
        return ForgeConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc


def load_config_from_project(project_root: Path | None = None) -> ForgeConfig:
    """Load config from a Forge project root or nearest detected root."""

    root = project_root or find_project_root()
    return load_config(root / ".forge" / "config.yaml")
