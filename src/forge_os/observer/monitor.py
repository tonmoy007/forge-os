"""Observer monitor — daemonized ACP health checks and metrics (P10.10-14).

The observer runs inside the Forge daemon and watches the ACP subsystem:
registry reachability, stale session cleanup, unhealthy-agent restarts, and
per-agent uptime/restart metrics. Failures surface as `DaemonAlert` entries
via `DaemonStateStore` so `forge status` can render them.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import ValidationError

from forge_os.config.loader import ConfigError, load_config
from forge_os.core.state_manager import utc_now
from forge_os.daemon.state import DaemonStateError, DaemonStateStore
from forge_os.kernel.acp_client import ACPClient
from forge_os.kernel.acp_registry_adapter import ACPRegistryAdapter
from forge_os.schemas.daemon import DaemonAlert
from forge_os.schemas.observer import AgentMetrics, ObserverConfig, ObserverMetrics

log = logging.getLogger("forge.observer")

METRICS_FILE_NAME = "metrics.json"


def load_observer_config(project_root: Path) -> ObserverConfig:
    """Read `features.observer` from `.forge/config.yaml`; default is disabled.

    Accepts `observer: true` (enable with defaults) or a mapping validated as
    `ObserverConfig`. Missing or invalid config never raises — the observer
    simply stays disabled so the daemon can keep running.
    """

    config_path = project_root / ".forge" / "config.yaml"
    if not config_path.exists():
        return ObserverConfig()
    try:
        features = load_config(config_path).features
    except ConfigError as exc:
        log.warning("observer disabled: could not load %s: %s", config_path, exc)
        return ObserverConfig()

    raw = features.get("observer")
    if raw is True:
        return ObserverConfig(enabled=True)
    if isinstance(raw, dict):
        try:
            return ObserverConfig.model_validate(raw)
        except ValidationError as exc:
            log.warning("observer disabled: invalid `features.observer` section: %s", exc)
            return ObserverConfig()
    return ObserverConfig()


class ObserverMonitor:
    """ACP health monitor: registry checks, session cleanup, restarts, metrics.

    Dependencies are injectable for deterministic tests: `now` (RFC 3339
    string clock), `registry` (ACP registry adapter), and `client_factory`
    (builds an ACPClient-like object from an agent command list).
    """

    def __init__(
        self,
        project_root: Path,
        forge_dir: Path | None = None,
        *,
        now: Callable[[], str] | None = None,
        config: ObserverConfig | None = None,
        registry: ACPRegistryAdapter | None = None,
        client_factory: Callable[[list[str]], Any] | None = None,
    ) -> None:
        self.project_root = project_root
        self.config = config or load_observer_config(project_root)
        self._now = now or utc_now
        self._store = DaemonStateStore(forge_dir)
        self._registry = registry or ACPRegistryAdapter(project_root / ".forge" / "acp")
        self._client_factory = client_factory or (lambda command: ACPClient(command))
        self.metrics_path = self._store.daemon_dir / METRICS_FILE_NAME
        # Restart attempts since the last metrics collection, per agent id.
        self._restart_counts: dict[str, int] = {}
        # Agents whose last restart attempt failed; their uptime stops accruing.
        self._unhealthy_agents: set[str] = set()

    # ── P09.18: registry health ────────────────────────────────────────────

    def check_registry(self) -> dict[str, Any]:
        """Check ACP registry reachability; alert at warning when unreachable."""

        accessible = self._registry.is_registry_accessible()
        alerted = False
        if not accessible:
            alerted = self._alert(
                source="acp-registry",
                severity="warning",
                message="ACP registry is not accessible.",
            )
        return {"accessible": accessible, "alerted": alerted}

    # ── P10.12: stale session cleanup ──────────────────────────────────────

    def cleanup_stale_sessions(self) -> dict[str, Any]:
        """Close sessions older than the stale threshold on every installed agent.

        Agents that cannot be reached are counted as errors and raise a
        warning alert; one bad agent never blocks the others.
        """

        max_age = self.config.stale_session_max_age_seconds
        now_dt = _parse_timestamp(self._now())
        checked = closed = errors = 0
        for agent in self._installed_agents():
            agent_id = str(agent.get("id", "unknown"))
            client = self._client_factory(_agent_command(agent))
            try:
                client.start()
                sessions = client.session_list()
            except Exception as exc:  # boundary to an external agent process
                errors += 1
                log.warning("cannot reach agent %s for session cleanup: %s", agent_id, exc)
                self._alert(
                    source="acp-sessions",
                    severity="warning",
                    message=f"Could not list sessions for agent '{agent_id}': {exc}",
                    metadata={"agent_id": agent_id},
                )
                self._stop_quietly(client, agent_id)
                continue
            for session in sessions:
                checked += 1
                age = _session_age_seconds(session, now_dt)
                if age is None or age <= max_age:
                    continue
                try:
                    client.session_close(session.id)
                    closed += 1
                except Exception as exc:  # boundary to an external agent process
                    errors += 1
                    log.warning(
                        "failed to close stale session %s on agent %s: %s",
                        session.id,
                        agent_id,
                        exc,
                    )
            self._stop_quietly(client, agent_id)
        return {"checked": checked, "closed": closed, "errors": errors}

    # ── P10.13: unhealthy agent restart ────────────────────────────────────

    def restart_unhealthy_agents(self) -> dict[str, Any]:
        """Probe each installed agent; attempt one restart when unhealthy.

        Alerts: info on recovery after restart, critical on restart failure.
        """

        checked = healthy = restarted = failed = 0
        for agent in self._installed_agents():
            agent_id = str(agent.get("id", "unknown"))
            checked += 1
            client = self._client_factory(_agent_command(agent))
            if self._probe(client, agent_id):
                healthy += 1
                self._unhealthy_agents.discard(agent_id)
                continue
            self._restart_counts[agent_id] = self._restart_counts.get(agent_id, 0) + 1
            if self._probe(client, agent_id):
                restarted += 1
                self._unhealthy_agents.discard(agent_id)
                self._alert(
                    source="acp-agents",
                    severity="info",
                    message=f"Agent '{agent_id}' recovered after restart.",
                    metadata={"agent_id": agent_id},
                )
            else:
                failed += 1
                self._unhealthy_agents.add(agent_id)
                self._alert(
                    source="acp-agents",
                    severity="critical",
                    message=f"Agent '{agent_id}' is unhealthy and failed to restart.",
                    metadata={"agent_id": agent_id},
                )
        return {"checked": checked, "healthy": healthy, "restarted": restarted, "failed": failed}

    # ── P10.14: metrics ────────────────────────────────────────────────────

    def collect_metrics(self) -> dict[str, Any]:
        """Accrue per-agent uptime/restart counters into metrics.json (atomic).

        Uptime accrues per collection interval for agents not currently
        marked unhealthy; restart attempts recorded since the previous
        collection are folded into the persisted totals.
        """

        metrics = self.load_metrics() or ObserverMetrics()
        now_str = self._now()
        elapsed = 0.0
        if metrics.collected_at is not None:
            previous = _parse_timestamp(metrics.collected_at)
            elapsed = max((_parse_timestamp(now_str) - previous).total_seconds(), 0.0)
        for agent in self._installed_agents():
            agent_id = str(agent.get("id", "unknown"))
            entry = metrics.agents.get(agent_id) or AgentMetrics()
            if agent_id not in self._unhealthy_agents:
                entry.uptime_seconds += elapsed
            entry.restarts += self._restart_counts.pop(agent_id, 0)
            entry.last_check = now_str
            metrics.agents[agent_id] = entry
        metrics.collected_at = now_str
        self._write_metrics(metrics)
        return {
            "collected_at": now_str,
            "agents": {name: entry.model_dump() for name, entry in metrics.agents.items()},
            "path": str(self.metrics_path),
        }

    def load_metrics(self) -> ObserverMetrics | None:
        """Return the persisted metrics snapshot, or None when missing/corrupt."""

        if not self.metrics_path.exists():
            return None
        try:
            raw = json.loads(self.metrics_path.read_text(encoding="utf-8"))
            return ObserverMetrics.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            log.warning("ignoring unreadable observer metrics at %s: %s", self.metrics_path, exc)
            return None

    # ── Internals ──────────────────────────────────────────────────────────

    def _installed_agents(self) -> list[dict[str, Any]]:
        return self._registry.get_installed_agents()

    def _probe(self, client: Any, agent_id: str) -> bool:
        """Start the agent, verify the process responds, and stop it again."""

        try:
            client.start()
            running = bool(client.is_running)
        except Exception as exc:  # boundary to an external agent process
            log.warning("agent %s did not start: %s", agent_id, exc)
            self._stop_quietly(client, agent_id)
            return False
        self._stop_quietly(client, agent_id)
        return running

    @staticmethod
    def _stop_quietly(client: Any, agent_id: str) -> None:
        try:
            client.stop()
        except Exception as exc:  # boundary to an external agent process
            log.warning("failed to stop client for agent %s: %s", agent_id, exc)

    def _alert(
        self,
        *,
        source: str,
        severity: Literal["info", "warning", "critical"],
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Record a daemon alert; False when no daemon state exists to hold it."""

        alert = DaemonAlert(
            alert_id=str(uuid4()),
            created_at=self._now(),
            source=source,
            severity=severity,
            message=message,
            metadata=metadata or {},
        )
        try:
            _ = self._store.add_alert(alert)
        except DaemonStateError as exc:
            log.warning("dropped %s alert from %s (%s): %s", severity, source, message, exc)
            return False
        return True

    def _write_metrics(self, metrics: ObserverMetrics) -> None:
        """Atomically persist metrics (tempfile + replace), creating parent dirs."""

        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(metrics.model_dump(), indent=2) + "\n"
        temp_path = self.metrics_path.with_name(f".{self.metrics_path.name}.tmp-{uuid4()}")
        try:
            _ = temp_path.write_text(content, encoding="utf-8")
            os.replace(temp_path, self.metrics_path)
        except OSError:
            temp_path.unlink(missing_ok=True)
            raise


def _agent_command(agent: dict[str, Any]) -> list[str]:
    """Split an installed agent's `install_path` into an argv list."""

    return shlex.split(str(agent.get("install_path", "")))


def _session_age_seconds(session: Any, now_dt: datetime) -> float | None:
    """Age of a session from `updated_at`/`created_at` metadata; None if unknown."""

    raw = session.metadata.get("updated_at") or session.metadata.get("created_at")
    if not raw:
        return None
    try:
        return (now_dt - _parse_timestamp(str(raw))).total_seconds()
    except ValueError:
        log.warning("session %s has unparseable timestamp %r", session.id, raw)
        return None


def _parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, accepting the project's `Z` suffix."""

    return datetime.fromisoformat(value.replace("Z", "+00:00"))
