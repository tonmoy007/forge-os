import json
from pathlib import Path
from typing import Any
from forge_os.schemas.security import SecurityAuditEntry

class SecurityAuditLog:
    """Append-only security audit log."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.log_path = self.project_root / ".forge" / "security-audit.jsonl"

    def log(self, entry: SecurityAuditEntry) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.model_dump(mode="json"), sort_keys=False) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries
