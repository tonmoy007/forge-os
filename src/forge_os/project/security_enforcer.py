import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from forge_os.schemas.security import (
    SecurityAuditEntry,
    SecurityDecision,
    SecurityPolicy,
    SecurityProfile,
)


class SecurityEnforcer:
    """Enforces security profiles and audits actions."""

    def __init__(self, project_root: Path, profile: SecurityProfile, audit_log) -> None:
        self.project_root = project_root.resolve()
        self.profile = profile
        self.audit_log = audit_log

    def validate_action(
        self,
        actor: dict,
        action: str,
        target: Any = None,
        capability: str = None,
    ) -> SecurityDecision:
        """Check if an action is allowed by the security profile."""
        
        # Find matching capability rule
        rule = next((r for r in self.profile.capabilities if r.capability == capability), None)
        
        policy = rule.policy if rule else self.profile.default_policy
        
        decision = SecurityDecision.DENIED
        if policy == SecurityPolicy.ALLOW:
            decision = SecurityDecision.ALLOWED
        elif policy == SecurityPolicy.PROMPT:
            # In a real CLI, this would trigger a user prompt
            decision = SecurityDecision.WARNED 
        
        # Audit the decision
        if self.profile.audit_enabled:
            self.audit_log.log(SecurityAuditEntry(
                audit_id=f"AUD-{int(time.time()*1000)}",
                actor=actor,
                action=action,
                target=target,
                capability=capability,
                decision=decision,
                reason=f"Policy {policy} applied"
            ))
            
        return decision

    def run_command(
        self,
        actor: dict,
        command: Sequence[str],
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        """Runs a command with a timeout and security check."""
        
        # Check if command execution is allowed
        decision = self.validate_action(
            actor, "execute_command", target=command, capability="shell",
        )
        if decision == SecurityDecision.DENIED:
            raise PermissionError(f"Command execution denied by security profile: {command}")

        # Use a safe timeout to prevent hangs
        effective_timeout = timeout or 30
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=str(self.project_root)
            )
            return result
        except subprocess.TimeoutExpired as exc:
            # Audit the timeout
            if self.profile.audit_enabled:
                self.audit_log.log(SecurityAuditEntry(
                    audit_id=f"AUD-TO-{int(time.time()*1000)}",
                    actor=actor,
                    action="execute_command_timeout",
                    target=command,
                    capability="shell",
                    decision=SecurityDecision.FAILED,
                    reason=f"Command timed out after {effective_timeout}s"
                ))
            raise exc
