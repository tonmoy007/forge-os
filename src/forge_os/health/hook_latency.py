"""Hook latency health checker (FR-HD-005).

Reads the hook-execution timings recorded by the event bus (`hooks/timing.py`,
written on every `EventBus.emit`) and flags hooks that are *persistently* slow —
i.e. slow on average across several runs, not a single transient spike. This is
alert-only per SRS v4.1: a flagged hook is surfaced in `forge health check`, never
auto-disabled.
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

from forge_os.health.checker import HealthChecker, HealthResult
from forge_os.hooks.timing import HookTimingLog

# A hook averaging ≥ 1s is genuinely slow — lifecycle hooks are meant to be quick.
# `min_samples` keeps a single slow run from being mistaken for a persistent pattern.
# Both become configurable when HealthMonitorConfig lands (daemon-monitor S4).
DEFAULT_SLOW_THRESHOLD_MS = 1000.0
DEFAULT_MIN_SAMPLES = 3


class HookLatencyHealthChecker(HealthChecker):
    """Flag hooks whose mean execution time is persistently over budget."""

    def __init__(
        self,
        project_root: Path,
        *,
        slow_threshold_ms: float = DEFAULT_SLOW_THRESHOLD_MS,
        min_samples: int = DEFAULT_MIN_SAMPLES,
    ) -> None:
        self.project_root = Path(project_root)
        self.slow_threshold_ms = slow_threshold_ms
        self.min_samples = min_samples

    def check(self) -> HealthResult:
        timings = HookTimingLog(self.project_root / ".forge").read_all()
        if not timings:
            # Fresh project, or hooks disabled ⇒ nothing recorded ⇒ nothing to flag.
            return HealthResult(
                healthy=True,
                message="No hook timings recorded yet.",
                details={"hooks_tracked": 0},
            )

        durations: dict[str, list[float]] = defaultdict(list)
        for timing in timings:
            # A foreign/corrupt timings file can carry NaN/inf (the canonical writer
            # emits null, but read_all tolerates corruption). A non-finite sample must
            # be ignored, not silently poison a hook's mean and hide a real slow hook.
            if math.isfinite(timing.duration_ms):
                durations[timing.hook_name].append(timing.duration_ms)

        slow_hooks = []
        for hook_name, samples in durations.items():
            mean_ms = sum(samples) / len(samples)
            if len(samples) >= self.min_samples and mean_ms >= self.slow_threshold_ms:
                slow_hooks.append(
                    {
                        "hook_name": hook_name,
                        "samples": len(samples),
                        "mean_ms": round(mean_ms, 1),
                        "max_ms": round(max(samples), 1),
                    }
                )
        slow_hooks.sort(key=lambda hook: hook["mean_ms"], reverse=True)

        details = {
            "hooks_tracked": len(durations),
            "threshold_ms": self.slow_threshold_ms,
            "min_samples": self.min_samples,
            "slow_hooks": slow_hooks,
        }
        if not slow_hooks:
            return HealthResult(
                healthy=True,
                message=f"All {len(durations)} hook(s) within latency budget.",
                details=details,
            )

        names = ", ".join(str(hook["hook_name"]) for hook in slow_hooks)
        return HealthResult(
            healthy=False,
            message=(
                f"{len(slow_hooks)} hook(s) persistently slow "
                f"(mean ≥ {self.slow_threshold_ms:.0f}ms over ≥ {self.min_samples} runs): {names}."
            ),
            details=details,
            recommendations=[f"Review or optimize slow hook(s): {names}."],
        )
