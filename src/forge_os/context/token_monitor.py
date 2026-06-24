"""Per-session injected-context token budget monitor (FR-HD-003 / FR-TE-003).

Pure evaluator: grades how much of a stage's injected-context token budget was
consumed by ``ContextPruner.select()`` and classifies it ``ok`` / ``warn`` /
``error`` (FR-TE-003: warn at 80%, error at 100%). The executor calls this right
after ``select()`` and logs + records a ``TokenBudgetExceeded`` event on
warn/error — it never pauses the spawn.

Note: in the wired path a single ``select()`` is always <= budget (the pruner
omits any artifact that would exceed it), so real spawns realistically only emit
``warn``. The ``error`` tier exists for the pure evaluator (and any future caller
that aggregates across selections) and is unit-tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

DEFAULT_WARN_RATIO = 0.80

BudgetLevel = Literal["ok", "warn", "error"]


@dataclass(frozen=True)
class BudgetEvaluation:
    """Outcome of grading one stage's injected-context utilization."""

    total_tokens: int
    token_budget: int
    ratio: float
    level: BudgetLevel


def evaluate_session_budget(
    total_tokens: int,
    token_budget: int,
    *,
    warn_ratio: float = DEFAULT_WARN_RATIO,
) -> BudgetEvaluation:
    """Grade injected-context utilization: error at >=100%, warn at >=warn_ratio."""

    budget = max(int(token_budget), 0)
    used = max(int(total_tokens), 0)
    if budget > 0:
        ratio = used / budget
    else:
        # Degenerate budget: any usage is an overage, none is fine.
        ratio = 1.0 if used > 0 else 0.0

    if ratio >= 1.0:
        level: BudgetLevel = "error"
    elif ratio >= warn_ratio:
        level = "warn"
    else:
        level = "ok"
    return BudgetEvaluation(total_tokens=used, token_budget=budget, ratio=ratio, level=level)


def resolve_warn_ratio(features: dict[str, Any]) -> float:
    """Read ``features.token_monitor.warn_ratio``; default 0.80; ignore malformed values.

    ``features`` is an unvalidated ``dict[str, Any]`` from config, so every shape
    is guarded: a missing/non-dict ``token_monitor``, a non-numeric or boolean
    ``warn_ratio``, or an out-of-range value all fall back to the default.
    """

    monitor = features.get("token_monitor")
    if not isinstance(monitor, dict):
        return DEFAULT_WARN_RATIO
    raw = monitor.get("warn_ratio", DEFAULT_WARN_RATIO)
    # bool is an int subclass — reject it explicitly before the numeric check.
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return DEFAULT_WARN_RATIO
    ratio = float(raw)
    if not 0.0 < ratio <= 1.0:
        return DEFAULT_WARN_RATIO
    return ratio
