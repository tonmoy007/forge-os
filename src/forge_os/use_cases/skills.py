"""Phase 09 skill proposal, approval, and installation workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_os.memory.project_profiles import ProjectProfileStore


class SkillUseCases:
    """Business logic for skill proposal, approval, and installation."""

    def __init__(self, project_root: Path, forge_dir: Path | None = None) -> None:
        self.project_root = project_root
        base = forge_dir if forge_dir is not None else Path.home() / ".forge"
        self.profile_store = ProjectProfileStore(forge_dir=base)
        self._skills_dir = base / "skills"

    def propose_skill(self, name: str, description: str) -> dict[str, Any]:
        """Propose a new skill based on repeated patterns."""
        profile = self.profile_store.get_profile(str(self.project_root))
        skills_dir = self._skills_dir
        skills_dir.mkdir(parents=True, exist_ok=True)

        skill_file = skills_dir / f"{name}.yaml"
        if skill_file.exists():
            return {"status": "exists", "name": name, "path": str(skill_file)}

        import yaml
        skill_data = {
            "name": name,
            "description": description,
            "status": "proposed",
            "project_path": str(self.project_root),
            "patterns": list(profile.patterns) if profile else [],
        }
        skill_file.write_text(
            yaml.safe_dump(skill_data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return {"status": "proposed", "name": name, "path": str(skill_file)}

    def approve_skill(self, name: str) -> dict[str, Any]:
        """Approve a proposed skill for installation."""
        skill_file = self._skills_dir / f"{name}.yaml"
        if not skill_file.exists():
            return {"status": "not_found", "name": name}

        import yaml
        skill_data = yaml.safe_load(skill_file.read_text(encoding="utf-8"))
        if not isinstance(skill_data, dict):
            return {"status": "error", "name": name}

        skill_data["status"] = "approved"
        skill_file.write_text(
            yaml.safe_dump(skill_data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return {"status": "approved", "name": name}

    def list_skills(self) -> list[dict[str, Any]]:
        """List all skills in ~/.forge/skills/."""
        import yaml
        skills_dir = self._skills_dir
        if not skills_dir.exists():
            return []

        result: list[dict[str, Any]] = []
        for f in sorted(skills_dir.iterdir()):
            if f.suffix == ".yaml":
                try:
                    data = yaml.safe_load(f.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        result.append({
                            "name": data.get("name", f.stem),
                            "description": data.get("description", ""),
                            "status": data.get("status", "unknown"),
                        })
                except Exception:  # noqa: BLE001
                    pass
        return result

    def install_skill(self, name: str) -> dict[str, Any]:
        """Install an approved skill (mark as installed)."""
        skill_file = self._skills_dir / f"{name}.yaml"
        if not skill_file.exists():
            return {"status": "not_found", "name": name}

        import yaml
        skill_data = yaml.safe_load(skill_file.read_text(encoding="utf-8"))
        if not isinstance(skill_data, dict):
            return {"status": "error", "name": name}
        if skill_data.get("status") != "approved":
            return {"status": "not_approved", "name": name}

        skill_data["status"] = "installed"
        skill_file.write_text(
            yaml.safe_dump(skill_data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return {"status": "installed", "name": name}
