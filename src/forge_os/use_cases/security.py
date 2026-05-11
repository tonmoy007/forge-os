from pathlib import Path
from typing import Any

from forge_os.project.security_audit import SecurityAuditLog
from forge_os.project.security_enforcer import SecurityEnforcer
from forge_os.schemas.security import SecurityProfile


class SecurityUseCases:
    """Encapsulates business logic for security enforcement and auditing."""

    def __init__(self, project_root: Path) -> None:
        self.audit_log = SecurityAuditLog(project_root)
        # Default profile if none exists, can be extended to load from config
        self.profile = SecurityProfile(profile_id="default")
        self.enforcer = SecurityEnforcer(project_root, self.profile, self.audit_log)

    def get_audit_entries(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.audit_log.read_all()[-limit:]

    def validate_action(self, actor: dict, action: str, target: Any = None, capability: str = None) -> str:
        return self.enforcer.validate_action(actor, action, target, capability)