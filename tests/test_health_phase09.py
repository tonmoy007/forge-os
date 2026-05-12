"""Tests for Phase 09 health check subsystem."""

from __future__ import annotations

from pathlib import Path

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
