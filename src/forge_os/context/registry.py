"""Phase 07 artifact registry and ADG persistence."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from forge_os.context.models import (
    Artifact,
    ArtifactDocument,
    ArtifactGraph,
    ArtifactStatus,
    GraphEdge,
    GraphNode,
)


class ArtifactRegistryError(RuntimeError):
    """Raised when artifact registry operations fail."""


class ArtifactRegistry:
    """Manage `.forge/artifacts.json` and `.forge/adg.json`."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.registry_path = self.project_root / ".forge" / "artifacts.json"
        self.graph_path = self.project_root / ".forge" / "adg.json"

    def load(self) -> ArtifactDocument:
        if not self.registry_path.exists():
            return ArtifactDocument(schema_version="0.1", artifacts=[])
        try:
            raw = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ArtifactRegistryError(
                f"Could not read artifact registry: {self.registry_path}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise ArtifactRegistryError(
                f"Artifact registry is invalid JSON: {self.registry_path}"
            ) from exc
        try:
            return ArtifactDocument.model_validate(raw)
        except ValidationError as exc:
            raise ArtifactRegistryError(f"Invalid artifact registry: {exc}") from exc

    def save(self, document: ArtifactDocument) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        _ = self.registry_path.write_text(
            json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        self.save_graph(self.build_graph(document))

    def register(
        self,
        path: str,
        *,
        stage_id: str | None = None,
        dependencies: list[str] | None = None,
        kind: str = "file",
        metadata: dict[str, object] | None = None,
    ) -> Artifact:
        document = self.load()
        normalized_path = self._normalize_path(path)
        timestamp = utc_now()
        snapshot = self._snapshot(normalized_path)
        artifact = self._find(document, normalized_path)
        if artifact is None:
            artifact = Artifact(
                path=normalized_path,
                stage_id=stage_id,
                kind=kind,
                dependencies=dependencies or [],
                dependents=[],
                status=snapshot["status"],
                content_hash=snapshot["content_hash"],
                modified_at=snapshot["modified_at"],
                token_estimate=int(snapshot["token_estimate"] or 0),
                registered_at=timestamp,
                updated_at=timestamp,
                metadata=metadata or {},
            )
            document.artifacts.append(artifact)
        else:
            artifact.stage_id = stage_id or artifact.stage_id
            artifact.kind = kind
            artifact.dependencies = dependencies or artifact.dependencies
            artifact.status = snapshot["status"]
            artifact.content_hash = snapshot["content_hash"]
            artifact.modified_at = snapshot["modified_at"]
            artifact.token_estimate = int(snapshot["token_estimate"] or 0)
            artifact.updated_at = timestamp
            artifact.metadata.update(metadata or {})
        self._rebuild_dependents(document)
        self.save(document)
        return artifact

    def register_stage_outputs(self, stage_id: str, output_paths: list[str]) -> list[Artifact]:
        artifacts: list[Artifact] = []
        for output_path in sorted(set(output_paths)):
            artifacts.append(
                self.register(
                    output_path,
                    stage_id=stage_id,
                    dependencies=self._default_dependencies(stage_id),
                    metadata={"registered_by": "stage_agent"},
                )
            )
        return artifacts

    def refresh(self) -> ArtifactDocument:
        document = self.load()
        before_hashes = {artifact.path: artifact.content_hash for artifact in document.artifacts}
        for artifact in document.artifacts:
            snapshot = self._snapshot(artifact.path)
            new_status = snapshot["status"]
            new_hash = snapshot["content_hash"]
            changed = before_hashes.get(artifact.path) != new_hash
            if new_status == "missing":
                artifact.status = "missing"
            elif artifact.status != "stale":
                artifact.status = "fresh"
            artifact.content_hash = new_hash
            artifact.modified_at = snapshot["modified_at"]
            artifact.token_estimate = int(snapshot["token_estimate"] or 0)
            artifact.updated_at = utc_now()
            if changed and new_status != "missing":
                self._mark_downstream_stale(document, artifact.path)
        self._rebuild_dependents(document)
        self.save(document)
        return document

    def list(self, *, status: str | None = None, stage_id: str | None = None) -> list[Artifact]:
        artifacts = self.load().artifacts
        if status is not None:
            artifacts = [artifact for artifact in artifacts if artifact.status == status]
        if stage_id is not None:
            artifacts = [artifact for artifact in artifacts if artifact.stage_id == stage_id]
        return sorted(artifacts, key=lambda artifact: artifact.path)

    def stale_count(self) -> int:
        return len([artifact for artifact in self.load().artifacts if artifact.status == "stale"])

    def build_graph(self, document: ArtifactDocument | None = None) -> ArtifactGraph:
        document = document or self.load()
        nodes = [
            GraphNode(
                id=artifact.id,
                path=artifact.path,
                stage_id=artifact.stage_id,
                status=artifact.status,
            )
            for artifact in sorted(document.artifacts, key=lambda item: item.path)
        ]
        edges: list[GraphEdge] = []
        registered = {artifact.path for artifact in document.artifacts}
        for artifact in sorted(document.artifacts, key=lambda item: item.path):
            for dependency in sorted(artifact.dependencies):
                if dependency in registered:
                    edges.append(GraphEdge(source=dependency, target=artifact.path))
        return ArtifactGraph(nodes=nodes, edges=edges)

    def save_graph(self, graph: ArtifactGraph) -> None:
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        _ = self.graph_path.write_text(
            json.dumps(graph.model_dump(mode="json"), indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )

    def _snapshot(self, relative_path: str) -> dict[str, object]:
        path = self.project_root / relative_path
        if not path.exists() or not path.is_file():
            return {
                "status": "missing",
                "content_hash": None,
                "modified_at": None,
                "token_estimate": 0,
            }
        content = path.read_bytes()
        return {
            "status": "fresh",
            "content_hash": hashlib.sha256(content).hexdigest(),
            "modified_at": utc_now_from_mtime(path.stat().st_mtime),
            "token_estimate": estimate_tokens(content.decode("utf-8", errors="replace")),
        }

    def _default_dependencies(self, stage_id: str) -> list[str]:
        if stage_id == "srs":
            return []
        stages_path = self.project_root / "pipeline" / "stages.yaml"
        if not stages_path.exists():
            return []
        previous_outputs = [
            artifact.path
            for artifact in self.load().artifacts
            if artifact.stage_id is not None and artifact.stage_id != stage_id
        ]
        return sorted(previous_outputs)

    def _rebuild_dependents(self, document: ArtifactDocument) -> None:
        for artifact in document.artifacts:
            artifact.dependents = []
        by_path = {artifact.path: artifact for artifact in document.artifacts}
        for artifact in document.artifacts:
            for dependency in artifact.dependencies:
                dependency_artifact = by_path.get(dependency)
                if (
                    dependency_artifact is not None
                    and artifact.path not in dependency_artifact.dependents
                ):
                    dependency_artifact.dependents.append(artifact.path)
        for artifact in document.artifacts:
            artifact.dependents = sorted(artifact.dependents)

    def _mark_downstream_stale(self, document: ArtifactDocument, path: str) -> None:
        by_path = {artifact.path: artifact for artifact in document.artifacts}
        visited: set[str] = set()

        def mark(current: str) -> None:
            if current in visited:
                return
            visited.add(current)
            for artifact in document.artifacts:
                if current in artifact.dependencies:
                    artifact.status = "stale"
                    artifact.updated_at = utc_now()
                    mark(artifact.path)

        mark(path)
        if path in by_path and by_path[path].status != "missing":
            by_path[path].status = "fresh"

    def _find(self, document: ArtifactDocument, path: str) -> Artifact | None:
        for artifact in document.artifacts:
            if artifact.path == path:
                return artifact
        return None

    def _normalize_path(self, path: str) -> str:
        normalized = path.strip().replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/") or not normalized:
            raise ArtifactRegistryError("Artifact path must be non-empty and project-relative.")
        return normalized


def estimate_tokens(text: str) -> int:
    """Deterministically estimate tokens without provider-specific tokenizers."""

    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, (len(stripped) + 3) // 4)


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def utc_now_from_mtime(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=UTC).isoformat().replace("+00:00", "Z")


def coerce_status(value: str) -> ArtifactStatus:
    if value not in {"fresh", "stale", "missing"}:
        raise ArtifactRegistryError(f"Unsupported artifact status `{value}`.")
    return value  # type: ignore[return-value]
