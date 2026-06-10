from __future__ import annotations

from pathlib import Path

from forge_os.dreamer.digest import DailyDigestWriter
from forge_os.events.log import append_event
from forge_os.events.model import new_event


def _seed_event(
    project_root: Path,
    event_type: str,
    *,
    timestamp: str,
    stage_id: str | None = None,
    actor_type: str = "core",
    actor_id: str = "forge-os",
    payload: dict[str, object] | None = None,
) -> None:
    event = new_event(
        event_type,  # type: ignore[arg-type]
        stage_id=stage_id,
        actor_type=actor_type,
        actor_id=actor_id,
        payload=payload,
    )
    event.timestamp = timestamp
    append_event(project_root / ".forge" / "events.jsonl", event)


def _seed_busy_day(project_root: Path) -> None:
    _seed_event(project_root, "StageStarted", timestamp="2026-06-09T08:00:00Z", stage_id="srs")
    _seed_event(
        project_root,
        "SubagentStop",
        timestamp="2026-06-09T09:00:00Z",
        stage_id="srs",
        actor_type="adapter",
        actor_id="dummy",
        payload={"status": "completed"},
    )
    _seed_event(
        project_root,
        "GateCompleted",
        timestamp="2026-06-09T10:00:00Z",
        stage_id="srs",
        payload={"stage_id": "srs", "blocking_failed": False, "result_count": 2},
    )
    _seed_event(project_root, "StageCompleted", timestamp="2026-06-09T11:00:00Z", stage_id="srs")
    _seed_event(project_root, "SessionStart", timestamp="2026-06-10T08:00:00Z")


def test_digest_summarizes_only_that_days_events(tmp_path: Path) -> None:
    _seed_busy_day(tmp_path)

    path = DailyDigestWriter(tmp_path).write(for_date="2026-06-09")

    assert path == tmp_path / "pipeline" / "log" / "daily-2026-06-09.md"
    content = path.read_text(encoding="utf-8")
    assert "# Daily Digest — 2026-06-09" in content
    assert "Total events: 4" in content
    assert "- StageStarted: 1" in content
    assert "- SubagentStop: 1" in content
    assert "## Stage transitions" in content
    assert "`StageCompleted` stage=srs" in content
    assert "## Agent runs" in content
    assert "adapter=dummy stage=srs status=completed" in content
    assert "## Gate results" in content
    assert "blocking_failed=False result_count=2" in content
    assert "SessionStart" not in content


def test_returns_none_when_no_events_that_day(tmp_path: Path) -> None:
    _seed_busy_day(tmp_path)

    assert DailyDigestWriter(tmp_path).write(for_date="2026-06-08") is None
    assert not (tmp_path / "pipeline" / "log" / "daily-2026-06-08.md").exists()


def test_returns_none_when_event_log_missing(tmp_path: Path) -> None:
    assert DailyDigestWriter(tmp_path).write(for_date="2026-06-09") is None


def test_default_date_derives_from_injected_now(tmp_path: Path) -> None:
    _seed_busy_day(tmp_path)

    path = DailyDigestWriter(tmp_path).write(now="2026-06-10T23:59:59Z")

    assert path == tmp_path / "pipeline" / "log" / "daily-2026-06-10.md"
    content = path.read_text(encoding="utf-8")
    assert "Total events: 1" in content
    assert "- SessionStart: 1" in content


def test_rerun_overwrites_same_file_deterministically(tmp_path: Path) -> None:
    _seed_busy_day(tmp_path)
    writer = DailyDigestWriter(tmp_path)

    first = writer.write(for_date="2026-06-09")
    first_content = first.read_text(encoding="utf-8")
    second = writer.write(for_date="2026-06-09")

    assert first == second
    assert second.read_text(encoding="utf-8") == first_content
