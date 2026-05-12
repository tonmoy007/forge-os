"""Tests for Phase 09 health check subsystem."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_os.health.acp import ACPHealthChecker
from forge_os.health.adg import ADGHealthChecker
from forge_os.health.checker import HealthChecker, HealthResult
from forge_os.health.gates import GateHealthChecker
from forge_os.health.memory import MemoryHealthChecker
from forge_os.health.state import StateHealthChecker

# ── Works on any path (no project needed for basic coverage) ────────────────


class TestHealthCheckerBase:
    def test_health_result_defaults(self) -> None:
        r = HealthResult(healthy=True)
        assert r.healthy is True
        assert r.message == ""
        assert r.details == {}
        assert r.recommendations == []

    def test_health_checker_abstract(self) -> None:
        class TestChecker(HealthChecker):
            def check(self) -> HealthResult:
                return HealthResult(healthy=True, message="ok")

        assert TestChecker().check().healthy is True


class TestStateHealthChecker:
    def test_no_project_returns_unhealthy(self, tmp_path: Path) -> None:
        checker = StateHealthChecker(tmp_path)
        result = checker.check()
        assert result.healthy is False
        assert "state.json not found" in result.message

    def test_initialized_project_returns_healthy(self, tmp_path: Path) -> None:
        from forge_os.project.scaffold import initialize_project

        root = tmp_path / "proj"
        initialize_project(root, project_name="health-test", profile="minimal")

        checker = StateHealthChecker(root)
        result = checker.check()
        assert result.healthy is True
        assert "stages completed" in result.message


class TestGateHealthChecker:
    def test_no_gate_file_returns_unhealthy(self, tmp_path: Path) -> None:
        checker = GateHealthChecker(tmp_path)
        result = checker.check()
        assert result.healthy is False

    def test_project_with_gates_returns_healthy(self, tmp_path: Path) -> None:
        from forge_os.project.scaffold import initialize_project

        root = tmp_path / "proj"
        initialize_project(root, project_name="gate-test", profile="minimal")

        checker = GateHealthChecker(root)
        result = checker.check()
        assert result.healthy is True
        assert "enabled" in result.message


class TestADGHealthChecker:
    def test_empty_registry_returns_healthy(self, tmp_path: Path) -> None:
        checker = ADGHealthChecker(tmp_path)
        result = checker.check()
        # Empty artifact list is valid
        assert result.healthy is True
        assert "artifacts" in result.message

    def test_with_artifacts(self, tmp_path: Path) -> None:
        from forge_os.context.registry import ArtifactRegistry

        registry = ArtifactRegistry(tmp_path)
        registry.register("README.md", stage_id="srs")

        checker = ADGHealthChecker(tmp_path)
        result = checker.check()
        assert "1 artifacts" in result.message


class TestMemoryHealthChecker:
    def test_empty_store_returns_healthy(self, tmp_path: Path) -> None:
        checker = MemoryHealthChecker(tmp_path)
        result = checker.check()
        assert result.healthy is True
        assert "0 lessons" in result.message or "lessons" in result.message


class TestACPHealthChecker:
    def test_no_cache_returns_unhealthy(self, tmp_path: Path) -> None:
        checker = ACPHealthChecker(tmp_path)
        result = checker.check()
        assert result.healthy is False
        assert "cache directory not found" in result.message or "ACP" in result.message

    def test_with_cache(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / ".forge" / "acp"
        cache_dir.mkdir(parents=True)
        import json
        (cache_dir / "registry.json").write_text(json.dumps({"agents": []}))

        checker = ACPHealthChecker(tmp_path)
        result = checker.check()
        assert result.healthy is True


class TestHealthUseCases:
    def test_run_full_check(self, tmp_path: Path) -> None:
        from forge_os.project.scaffold import initialize_project
        from forge_os.use_cases.health import HealthUseCases

        root = tmp_path / "proj"
        initialize_project(root, project_name="full-test", profile="minimal")

        use_cases = HealthUseCases(root)
        report = use_cases.run_full_check()

        assert "state" in report
        assert "gates" in report
        assert "adg" in report
        assert "memory" in report
        assert "acp" in report

        # State should be healthy
        assert report["state"]["healthy"] is True

    def test_run_full_check_uninitialized(self, tmp_path: Path) -> None:
        from forge_os.use_cases.health import HealthUseCases

        use_cases = HealthUseCases(tmp_path)
        report = use_cases.run_full_check()

        # Individual checkers shouldn't crash the whole report
        # Some will be healthy, some not, but all should have results
        assert len(report) == 5
        for subsystem in report:
            assert "healthy" in report[subsystem]


# ── Global Memory tests (P09.08) ────────────────────────────────────────────


class TestGlobalLessonStore:
    @pytest.fixture
    def forge_dir(self, tmp_path: Path) -> Path:
        return tmp_path / ".forge"

    def test_load_empty(self, forge_dir: Path) -> None:
        from forge_os.memory.global_store import GlobalLessonStore

        store = GlobalLessonStore(forge_dir)
        doc = store.load()
        assert doc.global_lessons == []
        assert doc.usage == []

    def test_promote_lesson(self, forge_dir: Path) -> None:
        from forge_os.memory.global_store import GlobalLessonStore
        from forge_os.memory.models import Lesson

        store = GlobalLessonStore(forge_dir)

        lesson = Lesson(
            text="Always use type hints",
            confidence=0.9,
            tags=["python", "types"],
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        promoted = store.promote_lesson(lesson, "/projects/forge-os")
        assert promoted.id is not None
        assert promoted.status == "approved"

        doc2 = store.load()
        assert len(doc2.global_lessons) >= 1

    def test_promote_duplicate_by_text(self, forge_dir: Path) -> None:
        from forge_os.memory.global_store import GlobalLessonStore
        from forge_os.memory.models import Lesson

        store = GlobalLessonStore(forge_dir)
        lesson = Lesson(
            text="Dedup test lesson",
            confidence=0.8,
            tags=["test"],
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        first = store.promote_lesson(lesson, "/projects/a")
        second = store.promote_lesson(lesson, "/projects/b")
        assert first.id == second.id

    def test_suggest_promotions_after_threshold(self, forge_dir: Path) -> None:
        from forge_os.memory.global_store import GlobalLessonStore
        from forge_os.memory.models import Lesson

        store = GlobalLessonStore(forge_dir)
        lesson = Lesson(
            text="Multi-project lesson",
            confidence=0.8,
            tags=["multi"],
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        store.promote_lesson(lesson, "/projects/p1")
        store.promote_lesson(lesson, "/projects/p2")
        store.promote_lesson(lesson, "/projects/p3")

        suggestions = store.suggest_promotions(min_projects=3)
        assert len(suggestions) >= 1
        assert suggestions[0]["usage_count"] >= 3

    def test_usage_tracking(self, forge_dir: Path) -> None:
        from forge_os.memory.global_store import GlobalLessonStore
        from forge_os.memory.models import Lesson

        store = GlobalLessonStore(forge_dir)
        lesson = Lesson(
            text="Usage tracked lesson",
            confidence=0.7,
            tags=["usage"],
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        promoted = store.promote_lesson(lesson, "/projects/my-project")
        usage = store.get_usage(promoted.id)
        assert usage is not None
        assert usage.usage_count == 1
        assert "/projects/my-project" in usage.project_paths


class TestGlobalMemoryUseCases:
    def test_promote_nonexistent_lesson_returns_none(self, tmp_path: Path) -> None:
        from forge_os.use_cases.global_memory import GlobalMemoryUseCases

        uc = GlobalMemoryUseCases(tmp_path, forge_dir=tmp_path / ".forge")
        result = uc.promote_lesson("nonexistent-id")
        assert result is None

    def test_list_global_lessons(self, tmp_path: Path) -> None:
        from forge_os.use_cases.global_memory import GlobalMemoryUseCases

        uc = GlobalMemoryUseCases(tmp_path, forge_dir=tmp_path / ".forge")
        lessons = uc.list_global_lessons()
        assert isinstance(lessons, list)


# ── Project Profiles & Skill tests (P09.13-15) ────────────────────────────


class TestProjectProfileStore:
    @pytest.fixture
    def forge_dir(self, tmp_path: Path) -> Path:
        return tmp_path / ".forge"

    def test_load_empty(self, forge_dir: Path) -> None:
        from forge_os.memory.project_profiles import ProjectProfileStore

        store = ProjectProfileStore(forge_dir)
        doc = store.load()
        assert doc.profiles == []

    def test_upsert_new_profile(self, forge_dir: Path) -> None:
        from forge_os.memory.project_profiles import ProjectProfileStore

        store = ProjectProfileStore(forge_dir)
        profile = store.upsert_profile(
            "/projects/test",
            languages=["python"],
            frameworks=["pytest"],
            tools=["ruff"],
        )
        assert profile.project_path == "/projects/test"
        assert "python" in profile.languages

        loaded = store.get_profile("/projects/test")
        assert loaded is not None
        assert "pytest" in loaded.frameworks

    def test_upsert_merges_data(self, forge_dir: Path) -> None:
        from forge_os.memory.project_profiles import ProjectProfileStore

        store = ProjectProfileStore(forge_dir)
        store.upsert_profile("/p1", languages=["python"])
        store.upsert_profile("/p1", languages=["go"], tools=["gofmt"])

        profile = store.get_profile("/p1")
        assert profile is not None
        assert "python" in profile.languages
        assert "go" in profile.languages
        assert "gofmt" in profile.tools

    def test_add_pattern(self, forge_dir: Path) -> None:
        from forge_os.memory.project_profiles import ProjectProfileStore

        store = ProjectProfileStore(forge_dir)
        store.add_pattern("/projects/test", "uses_fastapi")
        store.add_pattern("/projects/test", "uses_fastapi")

        profile = store.get_profile("/projects/test")
        assert profile is not None
        assert profile.patterns == ["uses_fastapi"]


class TestSkillUseCases:
    @pytest.fixture
    def skill_uc(self, tmp_path: Path):
        from forge_os.use_cases.skills import SkillUseCases
        return SkillUseCases(tmp_path, forge_dir=tmp_path / ".forge")

    def test_propose_and_list(self, skill_uc) -> None:
        result = skill_uc.propose_skill("test-skill", "A test skill for testing")
        assert result["status"] == "proposed"

        skills = skill_uc.list_skills()
        names = [s["name"] for s in skills]
        assert "test-skill" in names

    def test_approve_skill(self, skill_uc) -> None:
        skill_uc.propose_skill("approve-me", "Skill to approve")
        result = skill_uc.approve_skill("approve-me")
        assert result["status"] == "approved"

    def test_install_requires_approval(self, skill_uc) -> None:
        skill_uc.propose_skill("install-test", "Skill for install test")
        result = skill_uc.install_skill("install-test")
        assert result["status"] == "not_approved"

    def test_install_after_approval(self, skill_uc) -> None:
        skill_uc.propose_skill("install-ok", "Skill to fully install")
        skill_uc.approve_skill("install-ok")
        result = skill_uc.install_skill("install-ok")
        assert result["status"] == "installed"


# ── ACP Health tests (P09.18-22) ────────────────────────────────────────────


class TestACPHealthUseCases:
    def test_check_registry_no_cache(self, tmp_path: Path) -> None:
        from forge_os.use_cases.acp_health import ACPHealthUseCases

        uc = ACPHealthUseCases(tmp_path)
        result = uc.check_registry_health()
        assert "registry_cached" in result
        assert result["registry_cached"] is False

    def test_check_registry_with_cache(self, tmp_path: Path) -> None:
        from forge_os.use_cases.acp_health import ACPHealthUseCases

        cache_dir = tmp_path / ".forge" / "acp"
        cache_dir.mkdir(parents=True)
        import json
        (cache_dir / "registry.json").write_text(json.dumps({"agents": []}))

        uc = ACPHealthUseCases(tmp_path)
        result = uc.check_registry_health()
        assert result["registry_cached"] is True

    def test_installed_agent_health_empty(self, tmp_path: Path) -> None:
        from forge_os.use_cases.acp_health import ACPHealthUseCases

        uc = ACPHealthUseCases(tmp_path)
        agents = uc.check_installed_agent_health()
        assert agents == []

    def test_installed_agent_health_with_agents(self, tmp_path: Path) -> None:
        from forge_os.use_cases.acp_health import ACPHealthUseCases

        cache_dir = tmp_path / ".forge" / "acp"
        cache_dir.mkdir(parents=True)
        import json
        (cache_dir / "installed.json").write_text(
            json.dumps({"test-agent": {"id": "test-agent", "name": "Test Agent", "version": "1.0"}})
        )

        uc = ACPHealthUseCases(tmp_path)
        agents = uc.check_installed_agent_health()
        assert len(agents) == 1
        assert agents[0]["agent_id"] == "test-agent"

    def test_stale_session_detection(self, tmp_path: Path) -> None:
        from forge_os.use_cases.acp_health import ACPHealthUseCases

        uc = ACPHealthUseCases(tmp_path)
        actions = uc.detect_and_clean_stale_sessions()
        assert isinstance(actions, list)

    def test_health_report_structure(self, tmp_path: Path) -> None:
        from forge_os.use_cases.acp_health import ACPHealthUseCases

        uc = ACPHealthUseCases(tmp_path)
        report = uc.get_health_report()
        assert "registry" in report
        assert "agents" in report
        assert "session_actions" in report
        assert "healthy" in report


# ── Hook test harness (P09.02) ──────────────────────────────────────────────


class TestHookHarness:
    def test_hook_registration_and_execution(self) -> None:
        """Hook harness: register a hook, fire event, verify execution."""
        from forge_os.events.model import new_event
        from forge_os.hooks.registry import HookRegistry

        registry = HookRegistry()
        results: list[str] = []

        def sample_hook(event):  # type: ignore[no-untyped-def]
            results.append(event.event_type)

        registry.register("StageStarted", sample_hook, name="test-hook", order=0)
        event = new_event("StageStarted", stage_id="build", actor_type="test", actor_id="t1")
        registry.run(event)

        assert len(results) == 1
        assert results[0] == "StageStarted"

    def test_multiple_hooks_in_order(self) -> None:
        """Hooks execute in registered order."""
        from forge_os.events.model import new_event
        from forge_os.hooks.registry import HookRegistry

        registry = HookRegistry()
        order: list[int] = []

        def make_hook(n: int):
            def hook(event):  # type: ignore[no-untyped-def]
                order.append(n)
            return hook

        et = "StageStarted"
        registry.register(et, make_hook(1), name="h1", order=1)
        registry.register(et, make_hook(2), name="h2", order=2)
        registry.register(et, make_hook(0), name="h0", order=0)

        registry.run(new_event(et, actor_type="test", actor_id="t"))
        assert order == [0, 1, 2]


# ── Gate simulation fixtures (P09.03-04) ──────────────────────────────────


class TestGateSimulations:
    def test_known_good_gate_passes(self, tmp_path: Path) -> None:
        """A gate expecting an existing file passes."""
        from forge_os.gates.coordinator import GateCoordinator
        from forge_os.gates.models import GateCriterion

        (tmp_path / "pipeline").mkdir()
        (tmp_path / "SRS.md").write_text("# Requirements\n")

        coordinator = GateCoordinator(tmp_path)
        gate = GateCriterion(
            id="good-gate",
            name="SRS exists",
            type="required_file",
            criteria={"path": "SRS.md"},
            enabled=True,
        )
        result = coordinator.evaluate_gate(gate)
        assert result.status == "pass"

    def test_known_bad_gate_fails(self, tmp_path: Path) -> None:
        """A gate expecting a missing file fails."""
        from forge_os.gates.coordinator import GateCoordinator
        from forge_os.gates.models import GateCriterion

        (tmp_path / "pipeline").mkdir()
        coordinator = GateCoordinator(tmp_path)
        gate = GateCriterion(
            id="bad-gate",
            name="Missing SRS",
            type="required_file",
            criteria={"path": "SRS.md"},
            enabled=True,
        )
        result = coordinator.evaluate_gate(gate)
        assert result.status == "fail"

    def test_pattern_gate_good(self, tmp_path: Path) -> None:
        """Pattern gate passes when pattern is found."""
        from forge_os.gates.coordinator import GateCoordinator
        from forge_os.gates.models import GateCriterion

        (tmp_path / "pipeline").mkdir()
        (tmp_path / "main.py").write_text("def main():\n    pass\n")
        coordinator = GateCoordinator(tmp_path)
        gate = GateCriterion(
            id="pattern-pass",
            name="Has main function",
            type="pattern",
            criteria={"path": "main.py", "pattern": r"def main\b"},
            enabled=True,
        )
        result = coordinator.evaluate_gate(gate)
        assert result.status == "pass"

    def test_pattern_gate_bad(self, tmp_path: Path) -> None:
        """Pattern gate fails when pattern is absent."""
        from forge_os.gates.coordinator import GateCoordinator
        from forge_os.gates.models import GateCriterion

        (tmp_path / "pipeline").mkdir()
        (tmp_path / "empty.py").write_text("# nothing\n")
        coordinator = GateCoordinator(tmp_path)
        gate = GateCriterion(
            id="pattern-fail",
            name="Missing main",
            type="pattern",
            criteria={"path": "empty.py", "pattern": r"def main\b"},
            enabled=True,
        )
        result = coordinator.evaluate_gate(gate)
        assert result.status == "fail"


# ── Knowledge integrity tests (P09.05-06) ──────────────────────────────────


class TestKnowledgeIntegrity:
    def test_scan_no_issues(self, tmp_path: Path) -> None:
        """No issues when lessons don't reference missing artifacts."""
        from forge_os.use_cases.knowledge import KnowledgeUseCases

        uc = KnowledgeUseCases(tmp_path)
        refs = uc.scan_lesson_references()
        assert refs == []

    def test_scan_conflicts_no_duplicates(self, tmp_path: Path) -> None:
        from forge_os.use_cases.knowledge import KnowledgeUseCases

        uc = KnowledgeUseCases(tmp_path)
        conflicts = uc.scan_lesson_conflicts()
        assert conflicts == []

    def test_token_report_empty(self, tmp_path: Path) -> None:
        from forge_os.use_cases.knowledge import KnowledgeUseCases

        uc = KnowledgeUseCases(tmp_path)
        report = uc.report_token_budget()
        assert report["total_artifacts"] == 0
        assert report["total_tokens"] == 0


# ── Final Phase 09 validation count ─────────────────────────────────────────


def test_phase09_test_count() -> None:
    """Placeholder to track total Phase 09 test count."""
    assert True
