"""Phase 09 project profile memory — per-project language, stack, tooling patterns."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError


class ProjectProfile(BaseModel):
    """Profile data for a single project."""

    project_path: str
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    last_updated: str = ""


class ProjectProfileDocument(BaseModel):
    """Persistence container for project profiles."""

    schema_version: str = "0.1"
    profiles: list[ProjectProfile] = Field(default_factory=list)


def get_global_forge_dir() -> Path:
    path = Path.home() / ".forge"
    path.mkdir(parents=True, exist_ok=True)
    return path


class ProjectProfileStore:
    """Manage ~/.forge/profiles.yaml — per-project profiles."""

    def __init__(self, forge_dir: Path | None = None) -> None:
        base = forge_dir if forge_dir is not None else get_global_forge_dir()
        self.path = base / "profiles.yaml"

    def load(self) -> ProjectProfileDocument:
        if not self.path.exists():
            return ProjectProfileDocument()
        try:
            raw = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return ProjectProfileDocument()
        if not isinstance(raw, dict):
            return ProjectProfileDocument()
        try:
            return ProjectProfileDocument.model_validate(raw)
        except ValidationError:
            return ProjectProfileDocument()

    def save(self, document: ProjectProfileDocument) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = yaml.safe_dump(
            document.model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=True,
        )
        self.path.write_text(content, encoding="utf-8")

    def get_profile(self, project_path: str) -> ProjectProfile | None:
        doc = self.load()
        for p in doc.profiles:
            if p.project_path == project_path:
                return p
        return None

    def upsert_profile(
        self,
        project_path: str,
        languages: list[str] | None = None,
        frameworks: list[str] | None = None,
        tools: list[str] | None = None,
    ) -> ProjectProfile:
        doc = self.load()
        profile = next(
            (p for p in doc.profiles if p.project_path == project_path),
            None,
        )
        if profile is None:
            from forge_os.core.state_manager import utc_now
            profile = ProjectProfile(
                project_path=project_path,
                last_updated=utc_now(),
            )
            doc.profiles.append(profile)

        if languages:
            for lang in languages:
                if lang not in profile.languages:
                    profile.languages.append(lang)
        if frameworks:
            for fw in frameworks:
                if fw not in profile.frameworks:
                    profile.frameworks.append(fw)
        if tools:
            for tool in tools:
                if tool not in profile.tools:
                    profile.tools.append(tool)

        from forge_os.core.state_manager import utc_now
        profile.last_updated = utc_now()
        self.save(doc)
        return profile

    def add_pattern(self, project_path: str, pattern: str) -> None:
        """Record a repeated action pattern for a project."""
        doc = self.load()
        profile = next(
            (p for p in doc.profiles if p.project_path == project_path),
            None,
        )
        if profile is None:
            from forge_os.core.state_manager import utc_now
            profile = ProjectProfile(project_path=project_path, last_updated=utc_now())
            doc.profiles.append(profile)
        if pattern not in profile.patterns:
            profile.patterns.append(pattern)
        from forge_os.core.state_manager import utc_now
        profile.last_updated = utc_now()
        self.save(doc)
