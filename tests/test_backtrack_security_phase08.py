"""Tests for Phase 08 backtrack and security components."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from forge_os.project.backtrack_registry import BacktrackRegistry
from forge_os.project.rework_planner import ReworkPlanner
from forge_os.project.security_audit import SecurityAuditLog
from forge_os.project.security_enforcer import SecurityEnforcer
from forge_os.schemas.backtrack import BacktrackStatus, BacktrackTicket
from forge_os.schemas.security import (
    CapabilityRule,
    SecurityAuditEntry,
    SecurityDecision,
    SecurityPolicy,
    SecurityProfile,
)

# ── Backtrack tests ──────────────────────────────────────────────────────────


class TestBacktrackRegistry:
    def test_create_and_list_tickets(self, tmp_path: Path) -> None:
        registry = BacktrackRegistry(tmp_path)
        ticket = BacktrackTicket(
            ticket_id="BT-000001",
            reason="Test failure",
            source_stage_id="build",
            target_stage_id="test",
        )
        registry.create_ticket(ticket)
        tickets = registry.list_tickets()
        assert len(tickets) == 1
        assert tickets[0].ticket_id == "BT-000001"
        assert tickets[0].status == BacktrackStatus.OPEN

    def test_get_ticket_by_id(self, tmp_path: Path) -> None:
        registry = BacktrackRegistry(tmp_path)
        ticket = BacktrackTicket(
            ticket_id="BT-000002",
            reason="Spec changed",
            source_stage_id="spec",
            target_stage_id="design",
        )
        registry.create_ticket(ticket)
        found = registry.get_ticket("BT-000002")
        assert found is not None
        assert found.reason == "Spec changed"

    def test_get_nonexistent_ticket(self, tmp_path: Path) -> None:
        registry = BacktrackRegistry(tmp_path)
        assert registry.get_ticket("BT-NONE") is None

    def test_update_ticket_status(self, tmp_path: Path) -> None:
        registry = BacktrackRegistry(tmp_path)
        ticket = BacktrackTicket(
            ticket_id="BT-000003",
            reason="Logic error",
            source_stage_id="impl",
            target_stage_id="test",
        )
        registry.create_ticket(ticket)
        updated = registry.update_ticket("BT-000003", status=BacktrackStatus.APPROVED)
        assert updated is not None
        assert updated.status == BacktrackStatus.APPROVED

    def test_update_nonexistent(self, tmp_path: Path) -> None:
        registry = BacktrackRegistry(tmp_path)
        assert registry.update_ticket("BT-NONE", status=BacktrackStatus.APPROVED) is None

    def test_list_empty(self, tmp_path: Path) -> None:
        registry = BacktrackRegistry(tmp_path)
        assert registry.list_tickets() == []

    def test_persistence_across_loads(self, tmp_path: Path) -> None:
        registry = BacktrackRegistry(tmp_path)
        ticket = BacktrackTicket(
            ticket_id="BT-PERSIST",
            reason="Persist test",
            source_stage_id="build",
            target_stage_id="deploy",
        )
        registry.create_ticket(ticket)

        # New instance reading from same path
        registry2 = BacktrackRegistry(tmp_path)
        tickets = registry2.list_tickets()
        assert len(tickets) == 1
        assert tickets[0].ticket_id == "BT-PERSIST"


class TestReworkPlanner:
    def test_create_ticket_generates_id(self, tmp_path: Path) -> None:
        planner = ReworkPlanner(tmp_path)
        ticket_id = planner.create_backtrack_ticket(
            reason="Rework needed",
            source_stage_id="design",
            target_stage_id="impl",
        )
        assert ticket_id.startswith("BT-")

    def test_approve_ticket(self, tmp_path: Path) -> None:
        planner = ReworkPlanner(tmp_path)
        ticket_id = planner.create_backtrack_ticket(
            reason="Approve test",
            source_stage_id="spec",
            target_stage_id="test",
        )
        assert planner.approve_ticket(ticket_id) is True

    def test_run_rework_without_approval_fails(self, tmp_path: Path) -> None:
        planner = ReworkPlanner(tmp_path)
        ticket_id = planner.create_backtrack_ticket(
            reason="No approval test",
            source_stage_id="build",
            target_stage_id="test",
        )
        assert planner.run_rework(ticket_id) is False

    def test_run_rework_with_approval(self, tmp_path: Path) -> None:
        planner = ReworkPlanner(tmp_path)
        ticket_id = planner.create_backtrack_ticket(
            reason="Full flow",
            source_stage_id="impl",
            target_stage_id="test",
        )
        planner.approve_ticket(ticket_id)
        assert planner.run_rework(ticket_id) is True

    def test_resolve_ticket(self, tmp_path: Path) -> None:
        planner = ReworkPlanner(tmp_path)
        ticket_id = planner.create_backtrack_ticket(
            reason="Resolve test",
            source_stage_id="build",
            target_stage_id="deploy",
        )
        assert planner.resolve_ticket(ticket_id) is True

    def test_resolve_clears_stale_flags(self, tmp_path: Path) -> None:
        """resolve_ticket clears stale flags from artifacts marked by run_rework."""
        from forge_os.context.registry import ArtifactRegistry

        # Register an artifact for the deploy stage
        registry = ArtifactRegistry(tmp_path)
        registry.register("output.txt", stage_id="deploy")

        planner = ReworkPlanner(tmp_path)
        ticket_id = planner.create_backtrack_ticket(
            reason="Stale clear test",
            source_stage_id="build",
            target_stage_id="deploy",
        )
        planner.approve_ticket(ticket_id)
        planner.run_rework(ticket_id)

        # Verify artifacts are stale
        document = registry.load()
        stale = [a for a in document.artifacts if a.status == "stale"]
        assert len(stale) > 0

        # Resolve and verify stale flags are cleared
        planner.resolve_ticket(ticket_id)
        document = registry.load()
        still_stale = [a for a in document.artifacts if a.status == "stale"]
        assert len(still_stale) == 0

    def test_get_downstream_stages(self, tmp_path: Path) -> None:
        """get_downstream_stages returns stages whose artifacts depend on target stage outputs."""
        from forge_os.context.registry import ArtifactRegistry

        registry = ArtifactRegistry(tmp_path)
        registry.register("spec.md", stage_id="spec")
        registry.register("impl.py", stage_id="impl", dependencies=["spec.md"])
        registry.register("test_impl.py", stage_id="test", dependencies=["impl.py"])

        planner = ReworkPlanner(tmp_path)
        # Changes to spec should affect impl and test
        downstream = planner.get_downstream_stages("spec")
        assert "impl" in downstream
        assert "test" in downstream

    def test_create_ticket_includes_downstream_stages(self, tmp_path: Path) -> None:
        """Creating a backtrack ticket tracks both artifacts and downstream stages."""
        from forge_os.context.registry import ArtifactRegistry

        registry = ArtifactRegistry(tmp_path)
        registry.register("design.doc", stage_id="design")
        registry.register("spec.md", stage_id="spec", dependencies=["design.doc"])
        registry.register("impl.py", stage_id="impl", dependencies=["spec.md"])

        planner = ReworkPlanner(tmp_path)
        ticket_id = planner.create_backtrack_ticket(
            reason="Full cascade test",
            source_stage_id="review",
            target_stage_id="design",
        )
        ticket = planner.backtrack_registry.get_ticket(ticket_id)
        assert ticket is not None
        # Should include artifacts from downstream stages
        assert "spec.md" in ticket.affected_artifacts
        assert "impl.py" in ticket.affected_artifacts


# ── Security tests ───────────────────────────────────────────────────────────


class TestSecurityEnforcer:
    @pytest.fixture
    def profile(self) -> SecurityProfile:
        return SecurityProfile(
            profile_id="test",
            default_policy=SecurityPolicy.DENY,
            capabilities=[
                CapabilityRule(
                    capability="shell",
                    policy=SecurityPolicy.ALLOW,
                ),
                CapabilityRule(
                    capability="write_state",
                    policy=SecurityPolicy.DENY,
                ),
            ],
        )

    @pytest.fixture
    def enforcer(self, tmp_path: Path, profile: SecurityProfile) -> SecurityEnforcer:
        audit = SecurityAuditLog(tmp_path)
        return SecurityEnforcer(tmp_path, profile, audit)

    def test_allowed_action(self, enforcer: SecurityEnforcer) -> None:
        result = enforcer.validate_action(
            actor={"id": "test"},
            action="execute_command",
            capability="shell",
        )
        assert result == SecurityDecision.ALLOWED

    def test_denied_action(self, enforcer: SecurityEnforcer) -> None:
        result = enforcer.validate_action(
            actor={"id": "test"},
            action="write_state",
            capability="write_state",
        )
        assert result == SecurityDecision.DENIED

    def test_default_deny_policy(self, enforcer: SecurityEnforcer) -> None:
        result = enforcer.validate_action(
            actor={"id": "test"},
            action="unknown_action",
            capability="unknown_capability",
        )
        assert result == SecurityDecision.DENIED

    def test_run_command_allowed(self, enforcer: SecurityEnforcer) -> None:
        result = enforcer.run_command(
            actor={"id": "test"},
            command=["echo", "hello"],
            timeout=5,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "hello"

    def test_run_command_timeout(self, enforcer: SecurityEnforcer) -> None:
        with pytest.raises(subprocess.TimeoutExpired):
            enforcer.run_command(
                actor={"id": "test"},
                command=["sleep", "10"],
                timeout=1,
            )


class TestSecurityAuditLog:
    def test_audit_log_create_and_read(self, tmp_path: Path) -> None:
        audit = SecurityAuditLog(tmp_path)
        entry = SecurityAuditEntry(
            audit_id="AUD-001",
            actor={"id": "test-user"},
            action="execute_command",
            capability="shell",
            decision=SecurityDecision.ALLOWED,
        )
        audit.log(entry)
        entries = audit.read_all()
        assert len(entries) == 1
        assert entries[0]["audit_id"] == "AUD-001"

    def test_audit_log_persistence(self, tmp_path: Path) -> None:
        audit = SecurityAuditLog(tmp_path)
        entry = SecurityAuditEntry(
            audit_id="AUD-002",
            actor={"id": "test-user"},
            action="write_file",
            decision=SecurityDecision.DENIED,
        )
        audit.log(entry)

        # New reader
        audit2 = SecurityAuditLog(tmp_path)
        entries = audit2.read_all()
        assert len(entries) == 1

    def test_audit_log_empty(self, tmp_path: Path) -> None:
        audit = SecurityAuditLog(tmp_path)
        assert audit.read_all() == []

    def test_audit_log_limit(self, tmp_path: Path) -> None:
        audit = SecurityAuditLog(tmp_path)
        for i in range(5):
            audit.log(
                SecurityAuditEntry(
                    audit_id=f"AUD-{i:03d}",
                    actor={"id": "test"},
                    action="test",
                    decision=SecurityDecision.ALLOWED,
                )
            )
        entries = audit.read_all()
        assert len(entries) == 5
