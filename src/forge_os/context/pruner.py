"""Phase 07 deterministic context pruning."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from forge_os.context.models import Artifact, ContextSelection, SelectedContextItem
from forge_os.context.registry import ArtifactRegistry


class ContextPrunerError(RuntimeError):
    """Raised when context selection cannot be completed."""


class ContextPruner:
    """Select registered artifact context within a deterministic token budget."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.registry = ArtifactRegistry(self.project_root)
        self.audit_path = self.project_root / ".forge" / "context-selections.jsonl"

    def select(self, stage_id: str, *, token_budget: int = 2000) -> ContextSelection:
        if token_budget < 1:
            raise ContextPrunerError("Context token budget must be positive.")

        document = self.registry.refresh()
        artifacts = {artifact.path: artifact for artifact in document.artifacts}
        priorities = self._spread_activation_priorities(stage_id, list(artifacts.values()))
        candidates = sorted(
            [artifact for artifact in artifacts.values() if artifact.path in priorities],
            key=lambda artifact: (priorities[artifact.path], artifact.path),
        )

        total_tokens = 0
        selected: list[SelectedContextItem] = []
        omitted: list[dict[str, object]] = []
        for artifact in candidates:
            if artifact.status != "fresh":
                omitted.append(
                    {
                        "path": artifact.path,
                        "reason": f"artifact_status_{artifact.status}",
                        "token_estimate": artifact.token_estimate,
                    }
                )
                continue
            if total_tokens + artifact.token_estimate > token_budget:
                omitted.append(
                    {
                        "path": artifact.path,
                        "reason": "token_budget_exceeded",
                        "token_estimate": artifact.token_estimate,
                    }
                )
                continue
            selected.append(
                SelectedContextItem(
                    artifact_id=artifact.id,
                    path=artifact.path,
                    priority=priorities[artifact.path],
                    token_estimate=artifact.token_estimate,
                    reason=self._reason(stage_id, artifact, priorities[artifact.path]),
                    content=self._read_artifact(artifact.path),
                )
            )
            total_tokens += artifact.token_estimate

        selection = ContextSelection(
            stage_id=stage_id,
            token_budget=token_budget,
            total_tokens=total_tokens,
            selected=selected,
            omitted=omitted,
            created_at=utc_now(),
        )
        self._append_audit(selection)
        return selection

    def _spread_activation_priorities(
        self,
        stage_id: str,
        artifacts: list[Artifact],
    ) -> dict[str, int]:
        stage_paths = sorted(
            artifact.path for artifact in artifacts if artifact.stage_id == stage_id
        )
        if not stage_paths:
            stage_paths = sorted(artifact.path for artifact in artifacts)

        by_path = {artifact.path: artifact for artifact in artifacts}
        priorities: dict[str, int] = {}

        def visit(path: str, priority: int) -> None:
            existing = priorities.get(path)
            if existing is not None and existing <= priority:
                return
            priorities[path] = priority
            artifact = by_path.get(path)
            if artifact is None:
                return
            for dependency in sorted(artifact.dependencies):
                visit(dependency, priority + 1)

        for stage_path in stage_paths:
            visit(stage_path, 0)
        return priorities

    def _read_artifact(self, relative_path: str) -> str:
        path = self.project_root / relative_path
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ContextPrunerError(
                f"Could not read selected artifact `{relative_path}`."
            ) from exc

    def _reason(self, stage_id: str, artifact: Artifact, priority: int) -> str:
        if artifact.stage_id == stage_id:
            return "stage_artifact"
        if priority > 0:
            return "dependency_traversal"
        return "fallback_artifact"

    def _append_audit(self, selection: ContextSelection) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as audit_log:
            _ = audit_log.write(
                json.dumps(selection.model_dump(mode="json"), sort_keys=False) + "\n"
            )


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
