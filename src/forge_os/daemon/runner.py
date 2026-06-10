"""Daemon entry point: `python -m forge_os.daemon.runner <project_root>` (P10.03)."""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import signal
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from forge_os.core.state_manager import utc_now
from forge_os.daemon.scheduler import TaskRunner
from forge_os.daemon.state import DaemonStateError, DaemonStateStore
from forge_os.daemon.tasks import build_scheduled_tasks
from forge_os.schemas.daemon import DaemonState


def main(argv: list[str] | None = None) -> int:
    """Run the daemon loop until SIGTERM/SIGINT, persisting state under forge_dir."""

    parser = argparse.ArgumentParser(prog="forge-daemon", description="Forge OS daemon runner.")
    parser.add_argument("project_root", help="Root of the Forge project to serve.")
    parser.add_argument("--forge-dir", default=None, help="Override the ~/.forge directory.")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    forge_dir = Path(args.forge_dir) if args.forge_dir else None

    store = DaemonStateStore(forge_dir)
    store.daemon_dir.mkdir(parents=True, exist_ok=True)
    logger = _configure_logger(store.log_path)

    state = DaemonState(
        daemon_id=f"daemon-{uuid4().hex}",
        pid=os.getpid(),
        project_root=str(project_root),
        started_at=utc_now(),
    )
    store.save(state)
    logger.info(
        "daemon started: id=%s pid=%d project_root=%s", state.daemon_id, state.pid, project_root
    )

    stop_event = threading.Event()

    def _handle_stop(signum: int, _frame: object) -> None:
        logger.info("received signal %d; stopping", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    def _on_result(name: str, result: dict[str, Any] | None) -> None:
        logger.info("task %s ok: %s", name, result)
        try:
            store.record_task_run(name, status="ok")
        except DaemonStateError:
            logger.exception("failed to record successful run of task %s", name)

    def _on_error(name: str, exc: Exception) -> None:
        logger.error("task %s failed: %s", name, exc)
        try:
            store.record_task_run(name, status="error", error=str(exc))
        except DaemonStateError:
            logger.exception("failed to record failed run of task %s", name)

    runner = TaskRunner(
        build_scheduled_tasks(project_root, forge_dir),
        on_result=_on_result,
        on_error=_on_error,
    )
    runner.run_forever(stop_event)

    # Graceful stop: keep state (run history, alerts) on disk; liveness is decided
    # by a pid probe, not by file presence. Stamp a final heartbeat before exit —
    # best-effort: a failed final write must not turn a clean stop into an error.
    try:
        final_state = store.load()
        if final_state is not None:
            final_state.last_heartbeat = utc_now()
            store.save(final_state)
    except DaemonStateError:
        logger.exception("failed to stamp final heartbeat during graceful stop")
    logger.info("daemon stopped: pid=%d", os.getpid())
    _close_logger(logger)
    return 0


def _configure_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("forge.daemon")
    logger.setLevel(logging.INFO)
    _close_logger(logger)
    # Rotation keeps an always-on daemon from growing the log without bound.
    handler = logging.handlers.RotatingFileHandler(
        log_path, encoding="utf-8", maxBytes=1_000_000, backupCount=3
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _close_logger(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


if __name__ == "__main__":
    raise SystemExit(main())
