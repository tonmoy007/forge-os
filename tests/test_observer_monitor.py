"""Tests for forge_os.observer.monitor (P10.10-14)."""

from __future__ import annotations

import json
from pathlib import Path

from forge_os.daemon.state import DaemonStateStore
from forge_os.kernel.acp_client import ACPClientError, SessionInfo
from forge_os.observer.monitor import ObserverMonitor, load_observer_config
from forge_os.schemas.daemon import DaemonState
from forge_os.schemas.observer import ObserverConfig

NOW = "2026-06-10T12:00:00Z"


class Clock:
    """Injectable RFC 3339 clock with a settable value."""

    def __init__(self, value: str = NOW) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


class FakeRegistry:
    """ACPRegistryAdapter stand-in: scripted accessibility and installed agents."""

    def __init__(self, *, accessible: bool = True, agents: list[dict] | None = None) -> None:
        self.accessible = accessible
        self.agents = agents or []

    def is_registry_accessible(self) -> bool:
        return self.accessible

    def get_installed_agents(self) -> list[dict]:
        return list(self.agents)


class FakeClient:
    """ACPClient stand-in: scripted start outcomes, sessions, and close errors."""

    def __init__(
        self,
        sessions: list[SessionInfo] | None = None,
        *,
        start_failures: int = 0,
        close_error: bool = False,
    ) -> None:
        self.sessions = sessions or []
        self.start_failures = start_failures
        self.close_error = close_error
        self.start_calls = 0
        self.stop_calls = 0
        self.closed: list[str] = []
        self._running = False

    def start(self) -> dict:
        self.start_calls += 1
        if self.start_calls <= self.start_failures:
            raise ACPClientError("agent failed to start")
        self._running = True
        return {}

    def stop(self) -> None:
        self.stop_calls += 1
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def session_list(self) -> list[SessionInfo]:
        return list(self.sessions)

    def session_close(self, session_id: str) -> None:
        if self.close_error:
            raise ACPClientError("close failed")
        self.closed.append(session_id)


def agent_record(agent_id: str = "agent-a") -> dict:
    return {
        "id": agent_id,
        "name": agent_id,
        "version": "1.0.0",
        "distribution_type": "npx",
        "install_path": "npx -y fake-agent@latest",
    }


def seed_daemon_state(forge_dir: Path) -> DaemonStateStore:
    store = DaemonStateStore(forge_dir)
    store.save(
        DaemonState(
            daemon_id="daemon-test",
            pid=4321,
            project_root="/tmp/project",
            started_at="2026-06-10T00:00:00Z",
        )
    )
    return store


def make_monitor(
    tmp_path: Path,
    *,
    registry: FakeRegistry,
    client: FakeClient | None = None,
    clock: Clock | None = None,
    config: ObserverConfig | None = None,
) -> ObserverMonitor:
    return ObserverMonitor(
        tmp_path / "project",
        forge_dir=tmp_path / "forge",
        now=clock or Clock(),
        config=config or ObserverConfig(enabled=True),
        registry=registry,  # type: ignore[arg-type]
        client_factory=lambda command: client,
    )


# ── load_observer_config ─────────────────────────────────────────────────────


def test_load_observer_config_defaults_to_disabled_without_config(tmp_path: Path) -> None:
    config = load_observer_config(tmp_path)

    assert config.enabled is False
    assert config.poll_interval_seconds == 60.0
    assert config.acp_session_cleanup_interval_seconds == 300.0
    assert config.metrics_interval_seconds == 300.0
    assert config.stale_session_max_age_seconds == 3600.0


def write_project_config(project_root: Path, observer_value: str) -> None:
    forge = project_root / ".forge"
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "config.yaml").write_text(
        "schema_version: '0.1'\n"
        "project:\n"
        "  name: demo\n"
        "features:\n"
        f"  observer: {observer_value}\n",
        encoding="utf-8",
    )


def test_load_observer_config_enabled_via_boolean_flag(tmp_path: Path) -> None:
    write_project_config(tmp_path, "true")

    config = load_observer_config(tmp_path)

    assert config.enabled is True
    assert config.poll_interval_seconds == 60.0


def test_load_observer_config_accepts_mapping_overrides(tmp_path: Path) -> None:
    write_project_config(tmp_path, "{enabled: true, poll_interval_seconds: 5}")

    config = load_observer_config(tmp_path)

    assert config.enabled is True
    assert config.poll_interval_seconds == 5.0


def test_load_observer_config_disabled_on_invalid_yaml(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir(parents=True)
    (forge / "config.yaml").write_text(": not yaml :", encoding="utf-8")

    assert load_observer_config(tmp_path).enabled is False


# ── check_registry (P09.18) ──────────────────────────────────────────────────


def test_check_registry_accessible_adds_no_alert(tmp_path: Path) -> None:
    store = seed_daemon_state(tmp_path / "forge")
    monitor = make_monitor(tmp_path, registry=FakeRegistry(accessible=True))

    result = monitor.check_registry()

    assert result == {"accessible": True, "alerted": False}
    state = store.load()
    assert state is not None and state.alerts == []


def test_check_registry_persistent_failure_alerts_once_not_per_poll(tmp_path: Path) -> None:
    # Anti-spam: identical consecutive alerts are suppressed by the store, so a
    # registry outage produces ONE alert, not one per 60s poll.
    store = seed_daemon_state(tmp_path / "forge")
    monitor = make_monitor(tmp_path, registry=FakeRegistry(accessible=False))

    first = monitor.check_registry()
    second = monitor.check_registry()

    assert first == {"accessible": False, "alerted": True}
    assert second == {"accessible": False, "alerted": True}
    state = store.load()
    assert state is not None
    assert len(state.alerts) == 1
    alert = state.alerts[0]
    assert alert.severity == "warning"
    assert alert.source == "acp-registry"
    assert alert.alert_id
    assert alert.created_at
    assert "registry" in alert.message.lower()


def test_check_registry_failure_without_daemon_state_drops_alert(tmp_path: Path) -> None:
    monitor = make_monitor(tmp_path, registry=FakeRegistry(accessible=False))

    result = monitor.check_registry()

    assert result == {"accessible": False, "alerted": False}


# ── cleanup_stale_sessions (P10.12) ──────────────────────────────────────────


def session(session_id: str, created_at: str | None) -> SessionInfo:
    metadata = {"created_at": created_at} if created_at else {}
    return SessionInfo(id=session_id, title=session_id, metadata=metadata)


def test_cleanup_closes_only_sessions_older_than_threshold(tmp_path: Path) -> None:
    seed_daemon_state(tmp_path / "forge")
    client = FakeClient(
        sessions=[
            session("stale", "2026-06-10T10:59:59Z"),  # 3601s old
            session("fresh", "2026-06-10T11:30:00Z"),  # 1800s old
        ]
    )
    monitor = make_monitor(
        tmp_path, registry=FakeRegistry(agents=[agent_record()]), client=client
    )

    result = monitor.cleanup_stale_sessions()

    assert result == {"checked": 2, "closed": 1, "errors": 0}
    assert client.closed == ["stale"]
    assert client.stop_calls == 1


def test_cleanup_keeps_session_exactly_at_threshold(tmp_path: Path) -> None:
    seed_daemon_state(tmp_path / "forge")
    client = FakeClient(sessions=[session("boundary", "2026-06-10T11:00:00Z")])  # 3600s old
    monitor = make_monitor(
        tmp_path, registry=FakeRegistry(agents=[agent_record()]), client=client
    )

    result = monitor.cleanup_stale_sessions()

    assert result == {"checked": 1, "closed": 0, "errors": 0}
    assert client.closed == []


def test_cleanup_keeps_session_without_timestamp(tmp_path: Path) -> None:
    seed_daemon_state(tmp_path / "forge")
    client = FakeClient(sessions=[session("ageless", None)])
    monitor = make_monitor(
        tmp_path, registry=FakeRegistry(agents=[agent_record()]), client=client
    )

    result = monitor.cleanup_stale_sessions()

    assert result == {"checked": 1, "closed": 0, "errors": 0}


def test_cleanup_unreachable_agent_counts_error_and_alerts_warning(tmp_path: Path) -> None:
    store = seed_daemon_state(tmp_path / "forge")
    client = FakeClient(start_failures=99)
    monitor = make_monitor(
        tmp_path, registry=FakeRegistry(agents=[agent_record()]), client=client
    )

    result = monitor.cleanup_stale_sessions()

    assert result == {"checked": 0, "closed": 0, "errors": 1}
    state = store.load()
    assert state is not None
    assert [a.severity for a in state.alerts] == ["warning"]
    assert state.alerts[0].source == "acp-sessions"


def test_cleanup_counts_close_failures_as_errors(tmp_path: Path) -> None:
    seed_daemon_state(tmp_path / "forge")
    client = FakeClient(sessions=[session("stale", "2026-06-10T09:00:00Z")], close_error=True)
    monitor = make_monitor(
        tmp_path, registry=FakeRegistry(agents=[agent_record()]), client=client
    )

    result = monitor.cleanup_stale_sessions()

    assert result == {"checked": 1, "closed": 0, "errors": 1}


# ── restart_unhealthy_agents (P10.13) ────────────────────────────────────────


def test_restart_healthy_agent_emits_no_alert(tmp_path: Path) -> None:
    store = seed_daemon_state(tmp_path / "forge")
    client = FakeClient()
    monitor = make_monitor(
        tmp_path, registry=FakeRegistry(agents=[agent_record()]), client=client
    )

    result = monitor.restart_unhealthy_agents()

    assert result == {"checked": 1, "healthy": 1, "restarted": 0, "failed": 0}
    state = store.load()
    assert state is not None and state.alerts == []
    assert client.stop_calls == 1


def test_restart_recovery_alerts_info(tmp_path: Path) -> None:
    store = seed_daemon_state(tmp_path / "forge")
    client = FakeClient(start_failures=1)
    monitor = make_monitor(
        tmp_path, registry=FakeRegistry(agents=[agent_record()]), client=client
    )

    result = monitor.restart_unhealthy_agents()

    assert result == {"checked": 1, "healthy": 0, "restarted": 1, "failed": 0}
    state = store.load()
    assert state is not None
    assert [a.severity for a in state.alerts] == ["info"]
    assert state.alerts[0].source == "acp-agents"


def test_restart_failure_alerts_critical(tmp_path: Path) -> None:
    store = seed_daemon_state(tmp_path / "forge")
    client = FakeClient(start_failures=2)
    monitor = make_monitor(
        tmp_path, registry=FakeRegistry(agents=[agent_record()]), client=client
    )

    result = monitor.restart_unhealthy_agents()

    assert result == {"checked": 1, "healthy": 0, "restarted": 0, "failed": 1}
    state = store.load()
    assert state is not None
    assert [a.severity for a in state.alerts] == ["critical"]


# ── collect_metrics (P10.14) ─────────────────────────────────────────────────


def test_collect_metrics_round_trip_and_uptime_accrual(tmp_path: Path) -> None:
    clock = Clock(NOW)
    monitor = make_monitor(
        tmp_path, registry=FakeRegistry(agents=[agent_record()]), clock=clock
    )

    first = monitor.collect_metrics()
    clock.value = "2026-06-10T12:05:00Z"
    second = monitor.collect_metrics()

    assert first["agents"]["agent-a"]["uptime_seconds"] == 0.0
    assert second["agents"]["agent-a"]["uptime_seconds"] == 300.0
    assert second["agents"]["agent-a"]["last_check"] == "2026-06-10T12:05:00Z"

    reloaded = monitor.load_metrics()
    assert reloaded is not None
    assert reloaded.collected_at == "2026-06-10T12:05:00Z"
    assert reloaded.agents["agent-a"].uptime_seconds == 300.0
    # Atomic write leaves no temp files behind.
    leftovers = [p.name for p in monitor.metrics_path.parent.iterdir() if "tmp" in p.name]
    assert leftovers == []


def test_collect_metrics_records_restarts_and_freezes_unhealthy_uptime(tmp_path: Path) -> None:
    seed_daemon_state(tmp_path / "forge")
    clock = Clock(NOW)
    client = FakeClient(start_failures=2)
    monitor = make_monitor(
        tmp_path,
        registry=FakeRegistry(agents=[agent_record()]),
        client=client,
        clock=clock,
    )

    _ = monitor.collect_metrics()
    _ = monitor.restart_unhealthy_agents()
    clock.value = "2026-06-10T12:05:00Z"
    result = monitor.collect_metrics()

    assert result["agents"]["agent-a"]["restarts"] == 1
    assert result["agents"]["agent-a"]["uptime_seconds"] == 0.0


def test_load_metrics_returns_none_when_missing_or_corrupt(tmp_path: Path) -> None:
    monitor = make_monitor(tmp_path, registry=FakeRegistry())

    assert monitor.load_metrics() is None

    monitor.metrics_path.parent.mkdir(parents=True, exist_ok=True)
    monitor.metrics_path.write_text("{not json", encoding="utf-8")
    assert monitor.load_metrics() is None


def test_collect_metrics_writes_valid_json_document(tmp_path: Path) -> None:
    monitor = make_monitor(tmp_path, registry=FakeRegistry(agents=[agent_record()]))

    _ = monitor.collect_metrics()

    raw = json.loads(monitor.metrics_path.read_text(encoding="utf-8"))
    assert raw["collected_at"] == NOW
    assert "agent-a" in raw["agents"]


def test_cleanup_stops_client_on_every_path(tmp_path: Path) -> None:
    # Resource lifecycle: the agent subprocess is stopped on success, list
    # failure, and close-error paths alike (try/finally in cleanup).
    seed_daemon_state(tmp_path / "forge")
    stale = session("s-old", "2026-06-09T00:00:00Z")
    ok_client = FakeClient(sessions=[stale])
    broken_client = FakeClient(start_failures=99)
    close_error_client = FakeClient(sessions=[stale], close_error=True)
    clients = iter([ok_client, broken_client, close_error_client])
    registry = FakeRegistry(
        agents=[agent_record("a-ok"), agent_record("a-broken"), agent_record("a-close-err")]
    )
    monitor = ObserverMonitor(
        tmp_path / "project",
        forge_dir=tmp_path / "forge",
        now=Clock(),
        config=ObserverConfig(enabled=True),
        registry=registry,  # type: ignore[arg-type]
        client_factory=lambda command: next(clients),
    )

    result = monitor.cleanup_stale_sessions()

    assert result["errors"] == 2  # unreachable agent + failed close
    assert ok_client.stop_calls == 1
    assert broken_client.stop_calls == 1
    assert close_error_client.stop_calls == 1


def test_metrics_round_trip_preserves_schema_version(tmp_path: Path) -> None:
    seed_daemon_state(tmp_path / "forge")
    monitor = make_monitor(
        tmp_path,
        registry=FakeRegistry(agents=[agent_record("a1")]),
        client=FakeClient(),
    )

    _ = monitor.collect_metrics()

    raw = json.loads((tmp_path / "forge" / "daemon" / "metrics.json").read_text())
    assert raw["schema_version"] == "0.1"
    assert raw["collected_at"]
