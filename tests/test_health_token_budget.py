"""Tests for TokenBudgetHealthChecker (FR-HD-003, daemon-monitor S3)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from forge_os.health.token_budget import TokenBudgetHealthChecker
from forge_os.project.scaffold import initialize_project
from forge_os.use_cases.health import HealthUseCases


def _project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Demo", profile="standard")
    return tmp_path


def _seed(root: Path, selections: list[dict]) -> None:
    path = root / ".forge" / "context-selections.jsonl"
    path.write_text(
        "".join(json.dumps(selection) + "\n" for selection in selections), encoding="utf-8"
    )


def _selection(stage_id: str, total_tokens: int, token_budget: int = 2000) -> dict:
    return {"stage_id": stage_id, "token_budget": token_budget, "total_tokens": total_tokens}


def _check(root: Path, warn_ratio: float = 0.80) -> object:
    return TokenBudgetHealthChecker(root, warn_ratio=warn_ratio).check()


class TestTokenBudgetHealthChecker:
    def test_no_selections_is_healthy(self, tmp_path: Path) -> None:
        result = _check(_project(tmp_path))
        assert result.healthy is True
        assert "No context selections recorded yet" in result.message
        assert result.details["selections"] == 0

    def test_within_budget_is_healthy(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, [_selection("srs", 1000), _selection("ux", 1200)])  # 0.50, 0.60 < 0.80
        result = _check(root)
        assert result.healthy is True
        assert "within token budget" in result.message
        assert result.details["over_budget"] == 0

    def test_warn_tier_selection_is_flagged(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, [_selection("srs", 1700)])  # 0.85 ≥ 0.80 ⇒ warn
        result = _check(root)
        assert result.healthy is False
        breach = result.details["breaches"][0]
        assert breach["stage_id"] == "srs"
        assert breach["level"] == "warn"
        assert result.recommendations

    def test_error_tier_selection_is_flagged(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, [_selection("srs", 2500)])  # ≥ 100% ⇒ error
        result = _check(root)
        assert result.healthy is False
        assert result.details["breaches"][0]["level"] == "error"

    def test_only_breaches_counted_and_sorted_by_ratio_desc(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(
            root,
            [
                _selection("ok", 800),  # 0.40 ⇒ ok, not flagged
                _selection("mild", 1700),  # 0.85 ⇒ warn
                _selection("severe", 2200),  # 1.10 ⇒ error
            ],
        )
        result = _check(root)
        assert result.healthy is False
        assert result.details["selections"] == 3
        assert [b["stage_id"] for b in result.details["breaches"]] == ["severe", "mild"]

    def test_malformed_and_partial_lines_are_skipped(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        path = root / ".forge" / "context-selections.jsonl"
        path.write_text(
            "\n".join(
                [
                    json.dumps(_selection("srs", 1900)),  # 0.95 ⇒ warn (valid)
                    "{ not json",  # corrupt
                    "123",  # valid JSON but not an object
                    json.dumps({"stage_id": "x", "token_budget": 2000}),  # missing total_tokens
                    json.dumps({"stage_id": "y", "total_tokens": "lots", "token_budget": 2000}),
                    # bool is an int subclass — must be rejected, not graded as used=1.
                    json.dumps({"stage_id": "b", "total_tokens": True, "token_budget": 2000}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        result = _check(root)
        assert result.details["selections"] == 1  # only the one valid record graded
        assert result.healthy is False
        assert result.details["breaches"][0]["stage_id"] == "srs"

    def test_warn_ratio_resolved_from_config(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, [_selection("srs", 1200)])  # 0.60: ok at default 0.80
        # Default checker (resolves config; default 0.80) ⇒ healthy.
        assert TokenBudgetHealthChecker(root).check().healthy is True
        # Lower the configured warn ratio to 0.50 ⇒ 0.60 now breaches.
        config_path = root / ".forge" / "config.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["features"]["token_monitor"] = {"warn_ratio": 0.50}
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        flagged = TokenBudgetHealthChecker(root).check()
        assert flagged.healthy is False
        assert flagged.details["warn_ratio"] == 0.50

    def test_broken_config_degrades_to_default_ratio(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, [_selection("srs", 1900)])  # 0.95 ≥ default 0.80 ⇒ warn
        # A whitespace-only required field makes a schema field_validator raise
        # schemas.config.ConfigError, which load_config does NOT wrap; the checker must
        # fall back to the default ratio and still grade, not crash.
        config_path = root / ".forge" / "config.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["default_adapter"] = "   "
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        result = TokenBudgetHealthChecker(root).check()
        assert result.healthy is False  # graded at default 0.80 ⇒ 0.95 still flagged
        assert result.details["warn_ratio"] == 0.80

    def test_empty_surfaces_in_full_health_report(self, tmp_path: Path) -> None:
        report = HealthUseCases(_project(tmp_path)).run_full_check()
        assert "token_budget" in report
        assert report["token_budget"]["healthy"] is True

    def test_full_report_flags_over_budget_selection(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, [_selection("srs", 1900)])  # 0.95 ≥ default 0.80 ⇒ warn
        report = HealthUseCases(root).run_full_check()
        assert report["token_budget"]["healthy"] is False
        assert "srs" in report["token_budget"]["message"]
