"""Phase 06 reflection storage."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from forge_os.core.state_manager import utc_now
from forge_os.memory.lessons import LessonStore
from forge_os.memory.models import Reflection, ReflectionDocument


class ReflectionStoreError(RuntimeError):
    """Raised when reflections cannot be stored or loaded."""


class ReflectionStore:
    """Store structured reflection files under `.forge/reflections/`."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.reflections_dir = self.project_root / ".forge" / "reflections"

    def add(
        self,
        *,
        event_type: str,
        summary: str,
        stage_id: str | None = None,
        observations: list[str] | None = None,
        lesson_ids: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Reflection:
        reflection = Reflection(
            stage_id=stage_id,
            event_type=event_type,
            summary=summary,
            observations=observations or [],
            lesson_ids=lesson_ids or [],
            created_at=utc_now(),
            metadata=metadata or {},
        )
        self.save(reflection)
        return reflection

    def record_stage_completion(self, stage_id: str) -> Reflection:
        """Capture a deterministic completion reflection and pending extraction queue item."""

        lesson = LessonStore(self.project_root).add(
            f"Review completed `{stage_id}` stage for reusable lessons before future work.",
            confidence=0.4,
            tags=["reflection", "stage-completion"],
            stage_id=stage_id,
            source="reflection",
            status="pending",
            metadata={"queued_by": "ReflectionStore.record_stage_completion"},
        )
        return self.add(
            event_type="StageCompleted",
            stage_id=stage_id,
            summary=f"Stage `{stage_id}` completed; reflection captured for lesson review.",
            observations=[
                "A stage completion occurred.",
                "A pending lesson extraction item was queued for human approval.",
            ],
            lesson_ids=[lesson.id],
            metadata={"lesson_extraction_status": "pending_approval"},
        )

    def save(self, reflection: Reflection) -> None:
        self.reflections_dir.mkdir(parents=True, exist_ok=True)
        path = self.reflections_dir / f"{reflection.created_at}-{reflection.id}.yaml"
        safe_path = Path(str(path).replace(":", "-"))
        document = ReflectionDocument(reflection=reflection)
        content = yaml.safe_dump(
            document.model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=True,
        )
        _ = safe_path.write_text(content, encoding="utf-8")

    def list(self, *, stage_id: str | None = None) -> list[Reflection]:
        if not self.reflections_dir.exists():
            return []
        reflections: list[Reflection] = []
        for path in sorted(self.reflections_dir.glob("*.yaml")):
            reflections.append(self.load_file(path))
        if stage_id is not None:
            reflections = [
                reflection for reflection in reflections if reflection.stage_id == stage_id
            ]
        return sorted(reflections, key=lambda reflection: (reflection.created_at, reflection.id))

    def load_file(self, path: Path) -> Reflection:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ReflectionStoreError(f"Could not read reflection: {path}") from exc
        except yaml.YAMLError as exc:
            raise ReflectionStoreError(f"Reflection is not valid YAML: {path}") from exc

        if not isinstance(raw, dict):
            raise ReflectionStoreError(f"Reflection file must contain a YAML mapping: {path}")
        try:
            return ReflectionDocument.model_validate(raw).reflection
        except ValidationError as exc:
            raise ReflectionStoreError(f"Invalid reflection file {path}: {exc}") from exc

    def get(self, reflection_id: str) -> Reflection:
        for reflection in self.list():
            if reflection.id == reflection_id:
                return reflection
        raise ReflectionStoreError(f"Unknown reflection `{reflection_id}`.")
