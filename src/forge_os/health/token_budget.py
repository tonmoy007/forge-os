"""Per-session injected-context token budget health checker (FR-HD-003).

Reads the context-selection audit log the pruner already writes
(`.forge/context-selections.jsonl`) and flags selections whose injected-context
token count reached the budget warn ratio (FR-TE-003: warn at 80%, error at 100%),
reusing the pure `context/token_monitor.py` evaluator. Alert-only: a flagged
selection is surfaced in `forge health check`, never blocked or trimmed.

A "session" is one recorded selection — the pruner has no session id at its
boundary, so the audit log it already emits is the agreed measurement source
(SCOPE-observability-cost-backlog.md §#4 correction (b)).
"""

from __future__ import annotations

import json
from pathlib import Path

from forge_os.config.loader import ConfigError, load_config
from forge_os.context.token_monitor import (
    DEFAULT_WARN_RATIO,
    evaluate_session_budget,
    resolve_warn_ratio,
)
from forge_os.health.checker import HealthChecker, HealthResult
from forge_os.schemas.config import ConfigError as SchemaConfigError


class TokenBudgetHealthChecker(HealthChecker):
    """Flag context selections that reached the injected-context token budget."""

    SELECTIONS_FILE = "context-selections.jsonl"

    def __init__(self, project_root: Path, *, warn_ratio: float | None = None) -> None:
        self.project_root = Path(project_root)
        # None ⇒ resolve from config (features.token_monitor.warn_ratio); an explicit
        # value is for deterministic tests / callers that already know the ratio.
        self._warn_ratio = warn_ratio

    def check(self) -> HealthResult:
        records = self._read_selections(self.project_root / ".forge" / self.SELECTIONS_FILE)
        if not records:
            return HealthResult(
                healthy=True,
                message="No context selections recorded yet.",
                details={"selections": 0},
            )

        warn_ratio = (
            self._warn_ratio if self._warn_ratio is not None else self._resolve_warn_ratio()
        )
        breaches = []
        for record in records:
            evaluation = evaluate_session_budget(
                record["total_tokens"], record["token_budget"], warn_ratio=warn_ratio
            )
            if evaluation.level != "ok":
                breaches.append(
                    {
                        "stage_id": record.get("stage_id", "?"),
                        "total_tokens": evaluation.total_tokens,
                        "token_budget": evaluation.token_budget,
                        "ratio": round(evaluation.ratio, 3),
                        "level": evaluation.level,
                    }
                )
        breaches.sort(key=lambda breach: breach["ratio"], reverse=True)

        details = {
            "selections": len(records),
            "warn_ratio": warn_ratio,
            "over_budget": len(breaches),
            "breaches": breaches,
        }
        if not breaches:
            return HealthResult(
                healthy=True,
                message=f"All {len(records)} context selection(s) within token budget.",
                details=details,
            )

        stages = ", ".join(sorted({str(breach["stage_id"]) for breach in breaches}))
        return HealthResult(
            healthy=False,
            message=(
                f"{len(breaches)} of {len(records)} context selection(s) at "
                f"≥ {warn_ratio:.0%} of token budget: {stages}."
            ),
            details=details,
            recommendations=[f"Trim injected context for stage(s): {stages}."],
        )

    def _read_selections(self, path: Path) -> list[dict]:
        """Tolerant read of the append-only selection log; skip corrupt/partial lines."""
        if not path.exists():
            return []
        records: list[dict] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(record, dict):
                continue
            total = record.get("total_tokens")
            budget = record.get("token_budget")
            # bool is an int subclass — both counts must be real ints to be graded.
            if isinstance(total, bool) or isinstance(budget, bool):
                continue
            if not isinstance(total, int) or not isinstance(budget, int):
                continue
            records.append(record)
        return records

    def _resolve_warn_ratio(self) -> float:
        # load_config raises the loader's ConfigError (bad YAML / failed schema
        # validation) but the schema's field validators raise a *separate*
        # schemas.config.ConfigError that load_config does not wrap; catch both so a
        # broken config degrades to the default ratio instead of crashing the check.
        try:
            config = load_config(self.project_root / ".forge" / "config.yaml")
        except (ConfigError, SchemaConfigError):
            return DEFAULT_WARN_RATIO
        return resolve_warn_ratio(config.features)
