"""ADG and context health checker."""

from __future__ import annotations

from pathlib import Path

from forge_os.context.registry import ArtifactRegistry
from forge_os.health.checker import HealthChecker, HealthResult


class ADGHealthChecker(HealthChecker):
    """Check artifact dependency graph health."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def check(self) -> HealthResult:
        try:
            registry = ArtifactRegistry(self.project_root)
            document = registry.load()
        except Exception as exc:
            return HealthResult(
                healthy=False,
                message=f"Failed to load artifact registry: {exc}",
            )

        artifacts = document.artifacts
        total = len(artifacts)
        stale = sum(1 for a in artifacts if a.status == "stale")
        missing = sum(1 for a in artifacts if a.status == "missing")
        fresh = sum(1 for a in artifacts if a.status == "fresh")
        total_tokens = sum(a.token_estimate for a in artifacts)

        details = {
            "total_artifacts": total,
            "fresh": fresh,
            "stale": stale,
            "missing": missing,
            "total_token_estimate": total_tokens,
        }

        recommendations: list[str] = []
        if stale > 0:
            recommendations.append(f"{stale} stale artifacts. Run `forge artifact refresh`.")
        if missing > 0:
            recommendations.append(f"{missing} missing artifacts. Regenerate or remove them.")

        healthy = stale == 0 and missing == 0
        return HealthResult(
            healthy=healthy,
            message=f"{total} artifacts ({fresh} fresh, {stale} stale, {missing} missing).",
            details=details,
            recommendations=recommendations,
        )
