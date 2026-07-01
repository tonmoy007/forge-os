"""Tests for the always-on cost self-throttle (daemon-monitor S5, FR-COST-004)."""

from __future__ import annotations

from pathlib import Path

from forge_os.daemon.state import DaemonStateStore
from forge_os.daemon.throttle import (
    THROTTLE_RATIO,
    CostThrottle,
    ThrottleDecision,
    throttle_gate,
)
from forge_os.events.store import EventStore
from forge_os.schemas.daemon import DaemonState


def _seed_spend(root: Path, run_id: str, cost: object) -> None:
    store = EventStore(root / ".forge" / "events.db")
    store.append(
        run_id,
        "AdapterSpawnCompleted",
        {"adapter": "claude_code", "metadata": {"total_cost_usd": cost}},
    )
    store.close()


def _write_cap_config(root: Path, cost_cap_usd: float) -> None:
    forge = root / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "config.yaml").write_text(
        "schema_version: '0.1'\n"
        "project:\n  name: demo\n"
        "features:\n  health_monitor:\n"
        f"    cost_cap_usd: {cost_cap_usd}\n",
        encoding="utf-8",
    )


def _store_with_state(forge_dir: Path) -> DaemonStateStore:
    store = DaemonStateStore(forge_dir)
    store.save(
        DaemonState(
            daemon_id="daemon-test",
            pid=1234,
            project_root="/tmp/project",
            started_at="2026-06-10T00:00:00Z",
        )
    )
    return store


class TestCostThrottleEvaluate:
    def test_uncapped_never_throttles(self, tmp_path: Path) -> None:
        # No cap injected and no config ⇒ uncapped ⇒ not throttled.
        decision = CostThrottle(tmp_path).evaluate()
        assert decision == ThrottleDecision(
            throttled=False, spent_usd=0.0, cost_cap_usd=None, ratio=None
        )

    def test_non_positive_injected_cap_never_throttles(self, tmp_path: Path) -> None:
        _seed_spend(tmp_path, "r1", 5.0)
        decision = CostThrottle(tmp_path, cost_cap_usd=0.0).evaluate()
        assert decision.throttled is False
        assert decision.ratio is None

    def test_spend_below_ratio_does_not_throttle(self, tmp_path: Path) -> None:
        _seed_spend(tmp_path, "r1", 7.0)  # 7.0 / 10.0 = 0.70 < 0.80
        decision = CostThrottle(tmp_path, cost_cap_usd=10.0).evaluate()
        assert decision.throttled is False
        assert decision.ratio == 0.7

    def test_spend_at_ratio_boundary_throttles(self, tmp_path: Path) -> None:
        # Mutation guard for `>=` vs `>`: exactly at the ratio must throttle.
        _seed_spend(tmp_path, "r1", 8.0)  # 8.0 / 10.0 = 0.80 == THROTTLE_RATIO
        decision = CostThrottle(tmp_path, cost_cap_usd=10.0).evaluate()
        assert decision.ratio == THROTTLE_RATIO
        assert decision.throttled is True

    def test_spend_just_below_boundary_does_not_throttle(self, tmp_path: Path) -> None:
        # Paired with the boundary test above: 0.79 < 0.80 must NOT throttle.
        _seed_spend(tmp_path, "r1", 7.9)
        decision = CostThrottle(tmp_path, cost_cap_usd=10.0).evaluate()
        assert decision.throttled is False

    def test_spend_over_cap_throttles(self, tmp_path: Path) -> None:
        _seed_spend(tmp_path, "r1", 12.0)
        decision = CostThrottle(tmp_path, cost_cap_usd=10.0).evaluate()
        assert decision.throttled is True
        assert decision.ratio == 1.2

    def test_cap_resolved_from_config(self, tmp_path: Path) -> None:
        _write_cap_config(tmp_path, cost_cap_usd=10.0)
        _seed_spend(tmp_path, "r1", 9.0)  # 0.90 ≥ 0.80
        decision = CostThrottle(tmp_path).evaluate()  # cap resolved, not injected
        assert decision.cost_cap_usd == 10.0
        assert decision.throttled is True

    def test_broken_config_is_uncapped(self, tmp_path: Path) -> None:
        forge = tmp_path / ".forge"
        forge.mkdir(parents=True, exist_ok=True)
        (forge / "config.yaml").write_text("not: [a, mapping\n", encoding="utf-8")  # bad YAML
        _seed_spend(tmp_path, "r1", 100.0)
        decision = CostThrottle(tmp_path).evaluate()
        assert decision.throttled is False
        assert decision.cost_cap_usd is None

    def test_corrupt_events_db_fails_closed_when_capped(self, tmp_path: Path) -> None:
        # A corrupt events.db under a configured cap means spend is UNKNOWN. A spend
        # control must fail closed (throttle), not open — otherwise corrupting the
        # metering source silently defeats the cap. Must not raise out of the task.
        forge = tmp_path / ".forge"
        forge.mkdir(parents=True, exist_ok=True)
        (forge / "events.db").write_bytes(b"not a sqlite database\x00\xff")
        decision = CostThrottle(tmp_path, cost_cap_usd=10.0).evaluate()  # must not raise
        assert decision.throttled is True
        assert decision.reason == "store_unreadable"
        assert decision.ratio is None

    def test_corrupt_events_db_uncapped_does_not_throttle(self, tmp_path: Path) -> None:
        # No cap ⇒ no control to protect, so an unreadable store must not throttle
        # (there is nothing to fail closed on).
        forge = tmp_path / ".forge"
        forge.mkdir(parents=True, exist_ok=True)
        (forge / "events.db").write_bytes(b"not a sqlite database\x00\xff")
        decision = CostThrottle(tmp_path).evaluate()  # uncapped, no config
        assert decision.throttled is False
        assert decision.reason is None


class TestThrottleGate:
    def test_clear_runs_inner_and_records_no_alert(self, tmp_path: Path) -> None:
        forge_dir = tmp_path / "forge"
        store = _store_with_state(forge_dir)
        ran = {"called": False}

        def inner() -> dict[str, object] | None:
            ran["called"] = True
            return {"work": "done"}

        throttle = CostThrottle(tmp_path)  # uncapped ⇒ not throttled
        gated = throttle_gate(inner, throttle=throttle, store=store, task_name="dreamer-decay")

        result = gated()

        assert ran["called"] is True  # inner MUST have run
        assert result == {"work": "done"}  # its result passes through unchanged
        reloaded = store.load()
        assert reloaded is not None
        assert reloaded.alerts == []  # no alert on the clear path

    def test_throttled_skips_inner_and_records_one_alert(self, tmp_path: Path) -> None:
        forge_dir = tmp_path / "forge"
        store = _store_with_state(forge_dir)
        _seed_spend(tmp_path, "r1", 20.0)  # 20 / 10 = 2.0 ⇒ throttled
        ran = {"called": False}

        def inner() -> dict[str, object] | None:
            ran["called"] = True  # must NOT flip
            return {"work": "done"}

        throttle = CostThrottle(tmp_path, cost_cap_usd=10.0)
        gated = throttle_gate(inner, throttle=throttle, store=store, task_name="dreamer-decay")

        result = gated()

        assert ran["called"] is False  # inner MUST be skipped
        assert result is not None
        assert result["throttled"] is True
        assert result["task"] == "dreamer-decay"
        assert result["ratio"] == 2.0
        assert result["reason"] == "over_cap"
        reloaded = store.load()
        assert reloaded is not None
        assert len(reloaded.alerts) == 1
        alert = reloaded.alerts[0]
        assert alert.source == "cost-throttle"
        assert alert.severity == "warning"
        assert alert.metadata["task"] == "dreamer-decay"
        assert "cost cap reached" in alert.message

    def test_unreadable_store_fails_closed_and_alerts(self, tmp_path: Path) -> None:
        # The control-integrity path: a corrupt events.db under a cap must halt the
        # cost-incurring task (fail closed) with a distinct, honest alert.
        forge_dir = tmp_path / "forge"
        store = _store_with_state(forge_dir)
        (tmp_path / ".forge").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".forge" / "events.db").write_bytes(b"not a sqlite database\x00\xff")
        ran = {"called": False}

        def inner() -> dict[str, object] | None:
            ran["called"] = True
            return {"work": "done"}

        throttle = CostThrottle(tmp_path, cost_cap_usd=10.0)
        gated = throttle_gate(inner, throttle=throttle, store=store, task_name="dreamer-decay")

        result = gated()

        assert ran["called"] is False  # the cost-incurring task MUST be halted
        assert result is not None
        assert result["reason"] == "store_unreadable"
        reloaded = store.load()
        assert reloaded is not None
        assert len(reloaded.alerts) == 1
        assert "unreadable" in reloaded.alerts[0].message

    def test_repeated_throttle_dedups_to_one_alert(self, tmp_path: Path) -> None:
        forge_dir = tmp_path / "forge"
        store = _store_with_state(forge_dir)
        _seed_spend(tmp_path, "r1", 20.0)
        throttle = CostThrottle(tmp_path, cost_cap_usd=10.0)
        gated = throttle_gate(
            lambda: None, throttle=throttle, store=store, task_name="dreamer-decay"
        )

        _ = gated()
        _ = gated()
        _ = gated()

        reloaded = store.load()
        assert reloaded is not None
        assert len(reloaded.alerts) == 1  # consecutive duplicates suppressed

    def test_throttled_without_daemon_state_is_best_effort(self, tmp_path: Path) -> None:
        # No state saved ⇒ add_alert raises DaemonStateError; the gate swallows it
        # so a deliberate throttle never becomes a task failure.
        forge_dir = tmp_path / "forge"
        store = DaemonStateStore(forge_dir)  # deliberately no state
        _seed_spend(tmp_path, "r1", 20.0)
        ran = {"called": False}

        def inner() -> dict[str, object] | None:
            ran["called"] = True
            return None

        throttle = CostThrottle(tmp_path, cost_cap_usd=10.0)
        gated = throttle_gate(inner, throttle=throttle, store=store, task_name="dreamer-decay")

        result = gated()  # must not raise

        assert ran["called"] is False
        assert result is not None and result["throttled"] is True
        assert store.load() is None  # no state was created as a side effect
