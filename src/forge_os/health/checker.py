"""Base health check classes and result model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HealthResult:
    """Normalized result from a single health check."""

    healthy: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)


class HealthChecker(ABC):
    """Abstract base for a subsystem health checker."""

    @abstractmethod
    def check(self) -> HealthResult:
        """Run the health check and return a result."""
        ...
