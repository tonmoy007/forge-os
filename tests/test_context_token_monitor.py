"""Tests for the pure injected-context token budget evaluator (FR-HD-003 / FR-TE-003)."""

from __future__ import annotations

from forge_os.context.token_monitor import (
    DEFAULT_WARN_RATIO,
    evaluate_session_budget,
    resolve_warn_ratio,
)


class TestEvaluateSessionBudget:
    def test_ok_below_warn_ratio(self) -> None:
        result = evaluate_session_budget(1000, 2000)
        assert result.level == "ok"
        assert result.ratio == 0.5

    def test_warn_at_exact_warn_ratio(self) -> None:
        result = evaluate_session_budget(1600, 2000)  # 0.80
        assert result.level == "warn"

    def test_warn_between_ratio_and_full(self) -> None:
        assert evaluate_session_budget(1900, 2000).level == "warn"

    def test_just_below_warn_ratio_is_ok(self) -> None:
        assert evaluate_session_budget(1599, 2000).level == "ok"

    def test_error_at_exactly_full(self) -> None:
        result = evaluate_session_budget(2000, 2000)  # 1.0
        assert result.level == "error"

    def test_error_above_full(self) -> None:
        assert evaluate_session_budget(2500, 2000).level == "error"

    def test_custom_warn_ratio(self) -> None:
        assert evaluate_session_budget(1000, 2000, warn_ratio=0.4).level == "warn"

    def test_zero_budget_with_usage_is_error(self) -> None:
        result = evaluate_session_budget(10, 0)
        assert result.level == "error"
        assert result.ratio == 1.0

    def test_zero_budget_no_usage_is_ok(self) -> None:
        assert evaluate_session_budget(0, 0).level == "ok"

    def test_negative_inputs_are_clamped(self) -> None:
        result = evaluate_session_budget(-5, 2000)
        assert result.total_tokens == 0
        assert result.level == "ok"


class TestResolveWarnRatio:
    def test_default_when_no_token_monitor(self) -> None:
        assert resolve_warn_ratio({}) == DEFAULT_WARN_RATIO

    def test_default_when_warn_ratio_missing(self) -> None:
        assert resolve_warn_ratio({"token_monitor": {}}) == DEFAULT_WARN_RATIO

    def test_reads_valid_ratio(self) -> None:
        assert resolve_warn_ratio({"token_monitor": {"warn_ratio": 0.5}}) == 0.5

    def test_int_one_is_valid(self) -> None:
        assert resolve_warn_ratio({"token_monitor": {"warn_ratio": 1}}) == 1.0

    def test_default_when_token_monitor_not_a_dict(self) -> None:
        assert resolve_warn_ratio({"token_monitor": "nope"}) == DEFAULT_WARN_RATIO

    def test_default_on_non_numeric(self) -> None:
        assert resolve_warn_ratio({"token_monitor": {"warn_ratio": "high"}}) == DEFAULT_WARN_RATIO

    def test_default_on_bool(self) -> None:
        # bool is an int subclass — must not be accepted as a ratio.
        assert resolve_warn_ratio({"token_monitor": {"warn_ratio": True}}) == DEFAULT_WARN_RATIO

    def test_default_on_out_of_range(self) -> None:
        assert resolve_warn_ratio({"token_monitor": {"warn_ratio": 1.5}}) == DEFAULT_WARN_RATIO
        assert resolve_warn_ratio({"token_monitor": {"warn_ratio": 0}}) == DEFAULT_WARN_RATIO
        assert resolve_warn_ratio({"token_monitor": {"warn_ratio": -0.2}}) == DEFAULT_WARN_RATIO
