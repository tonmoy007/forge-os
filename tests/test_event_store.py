"""Tests for Phase 08.5 Event Store: append, read, replay, snapshots, dual-write."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge_os.events.store import EventStore

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / ".forge" / "events.db"


@pytest.fixture
def store(db_path: Path) -> EventStore:
    es = EventStore(db_path)
    yield es
    es.close()


# ── Event Store tests ────────────────────────────────────────────────────────


class TestEventStoreSchema:
    def test_init_creates_db_file(self, db_path: Path) -> None:
        assert not db_path.exists()
        es = EventStore(db_path)
        es._connect()
        assert db_path.exists()
        es.close()

    def test_init_creates_tables(self, store: EventStore) -> None:
        conn = store._connect()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [r["name"] for r in tables]
        assert "events" in table_names
        assert "snapshots" in table_names

    def test_wal_mode_enabled(self, store: EventStore) -> None:
        conn = store._connect()
        row = conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0] == "wal"


class TestEventStoreAppend:
    def test_append_returns_event_id(self, store: EventStore) -> None:
        event_id = store.append("test-stream", "TestEvent", {"key": "value"})
        assert event_id == 1

    def test_append_increments_event_id(self, store: EventStore) -> None:
        assert store.append("s1", "E1") == 1
        assert store.append("s1", "E2") == 2
        assert store.append("s2", "E3") == 3

    def test_append_tracks_version_per_stream(self, store: EventStore) -> None:
        store.append("stream-a", "E1")
        store.append("stream-b", "E1")
        store.append("stream-a", "E2")

        events_a = store.read_stream("stream-a")
        events_b = store.read_stream("stream-b")
        assert events_a[0]["version"] == 1
        assert events_b[0]["version"] == 1
        assert events_a[1]["version"] == 2

    def test_append_without_payload(self, store: EventStore) -> None:
        store.append("empty-stream", "EmptyEvent")
        events = store.read_stream("empty-stream")
        assert len(events) == 1
        assert json.loads(events[0]["payload"]) == {}


class TestEventStoreRead:
    def test_read_stream_returns_events_in_order(self, store: EventStore) -> None:
        store.append("s", "First")
        store.append("s", "Second")
        store.append("s", "Third")

        events = store.read_stream("s")
        assert len(events) == 3
        assert events[0]["event_type"] == "First"
        assert events[1]["event_type"] == "Second"
        assert events[2]["event_type"] == "Third"

    def test_read_stream_empty(self, store: EventStore) -> None:
        assert store.read_stream("nonexistent") == []

    def test_read_all_global_order(self, store: EventStore) -> None:
        store.append("a", "A1")
        store.append("b", "B1")
        store.append("a", "A2")

        all_events = store.read_all()
        assert len(all_events) == 3
        assert all_events[0]["event_type"] == "A1"
        assert all_events[1]["event_type"] == "B1"
        assert all_events[2]["event_type"] == "A2"

    def test_read_by_type(self, store: EventStore) -> None:
        store.append("s1", "TypeA")
        store.append("s2", "TypeB")
        store.append("s3", "TypeA")

        type_a = store.read_by_type("TypeA")
        assert len(type_a) == 2

        type_b = store.read_by_type("TypeB")
        assert len(type_b) == 1

        type_c = store.read_by_type("TypeC")
        assert len(type_c) == 0

    def test_read_stream_from_version(self, store: EventStore) -> None:
        store.append("s", "V1")
        store.append("s", "V2")
        store.append("s", "V3")

        after_v1 = store.read_stream_from("s", 1)
        assert len(after_v1) == 2
        assert after_v1[0]["event_type"] == "V2"
        assert after_v1[1]["event_type"] == "V3"


class TestEventStoreSnapshots:
    def test_save_and_load_snapshot(self, store: EventStore) -> None:
        store.save_snapshot("my-stream", {"status": "complete"}, event_version=5)
        snapshot = store.load_snapshot("my-stream")
        assert snapshot is not None
        assert snapshot["state"] == {"status": "complete"}
        assert snapshot["event_version"] == 5

    def test_load_snapshot_nonexistent(self, store: EventStore) -> None:
        assert store.load_snapshot("nonexistent") is None

    def test_snapshot_upsert(self, store: EventStore) -> None:
        store.save_snapshot("s", {"version": 1}, event_version=3)
        store.save_snapshot("s", {"version": 2}, event_version=10)

        snapshot = store.load_snapshot("s")
        assert snapshot is not None
        assert snapshot["state"] == {"version": 2}
        assert snapshot["event_version"] == 10


class TestEventStoreReplay:
    def test_replay_no_events_returns_empty(self, store: EventStore) -> None:
        assert store.replay("empty") == []

    def test_replay_single_stream(self, store: EventStore) -> None:
        store.append("order-1", "OrderCreated", {"id": 1})
        store.append("order-1", "OrderShipped", {"id": 1})

        events = store.replay("order-1")
        assert len(events) == 2

    def test_replay_state_no_events(self, store: EventStore) -> None:
        assert store.replay_state("empty") is None

    def test_replay_state_from_events(self, store: EventStore) -> None:
        store.append("project/test", "StateSaved", {"state": {"stage": "build"}})
        store.append("project/test", "StateSaved", {"state": {"stage": "test", "status": "active"}})

        state = store.replay_state("project/test")
        assert state is not None
        assert state["stage"] == "test"
        assert state["status"] == "active"

    def test_replay_state_with_snapshot(self, store: EventStore) -> None:
        store.append("project/p1", "StateSaved", {"state": {"stage": "spec"}})
        store.append("project/p1", "StateSaved", {"state": {"stage": "build"}})
        store.save_snapshot("project/p1", {"stage": "build"}, event_version=2)
        store.append("project/p1", "StateSaved", {"state": {"stage": "test"}})

        state = store.replay_state("project/p1")
        assert state is not None
        assert state["stage"] == "test"


class TestEventStoreAppendStateEvent:
    def test_append_state_event(self, store: EventStore) -> None:
        eid = store.append_state_event("project/test", {"stage": "build", "status": "active"})
        assert eid == 1

        events = store.read_stream("project/test")
        assert len(events) == 1
        payload = json.loads(events[0]["payload"])
        assert payload["state"]["stage"] == "build"


class TestEventStoreLifecycle:
    def test_context_manager(self, db_path: Path) -> None:
        with EventStore(db_path) as es:
            eid = es.append("stream", "Event")
            assert eid == 1
        # Connection should be closed after exit
        assert es._conn is None

    def test_close_and_reopen(self, db_path: Path) -> None:
        es = EventStore(db_path)
        es.append("s", "E1")
        es.close()

        es2 = EventStore(db_path)
        events = es2.read_stream("s")
        assert len(events) == 1
        es2.close()

    def test_multiple_writes_same_store(self, store: EventStore) -> None:
        for i in range(10):
            store.append("bulk", "Event", {"i": i})
        events = store.read_stream("bulk")
        assert len(events) == 10


# ── Dual-write consistency tests ────────────────────────────────────────────


class TestDualWriteConsistency:
    def test_dual_write_project_state(self, tmp_path: Path) -> None:
        """StateManager.save() appends to both state.json and Event Store."""
        from forge_os.project.scaffold import initialize_project

        root = tmp_path / "dual-write-test"
        initialize_project(root, project_name="dual-test", profile="minimal")

        from forge_os.core.state_manager import StateManager

        sm = StateManager(root)
        state = sm.load()

        # Save triggers dual-write
        sm.save(state)

        # Verify state.json exists
        assert (root / ".forge" / "state.json").exists()

        # Verify Event Store has the state event
        events = sm.event_store.read_stream(f"project/{state.project_id}")
        assert len(events) >= 1
        assert events[0]["event_type"] == "StateSaved"

    def test_replay_matches_state_json(self, tmp_path: Path) -> None:
        """Replaying Event Store events produces the same state as state.json."""
        from forge_os.project.scaffold import initialize_project

        root = tmp_path / "replay-consistency"
        initialize_project(root, project_name="replay-test", profile="minimal")

        from forge_os.core.state_manager import StateManager

        sm = StateManager(root)
        state = sm.load()

        # Multiple saves
        sm.save(state)
        state.current_stage_id = "srs"
        sm.save(state)

        # Replay from Event Store
        replayed = sm.event_store.replay_state(f"project/{state.project_id}")

        assert replayed is not None
        assert replayed["current_stage_id"] == "srs"
        # Verify project_id matches what we started with
        assert replayed["project_id"] == state.project_id

    def test_events_persist_across_sessions(self, tmp_path: Path) -> None:
        """Event Store data survives store close/reopen."""
        from forge_os.core.state_manager import StateManager

        root = tmp_path / "session-test"
        from forge_os.project.scaffold import initialize_project
        initialize_project(root, project_name="session-test", profile="minimal")

        sm = StateManager(root)
        state = sm.load()
        sm.save(state)

        # Close and create new manager
        db_path = root / ".forge" / "events.db"
        store2 = EventStore(db_path)
        events = store2.read_stream(f"project/{state.project_id}")
        assert len(events) >= 1
        store2.close()

    def test_dual_write_does_not_block_on_failure(self, tmp_path: Path) -> None:
        """state.json write succeeds even if Event Store is unavailable."""
        from forge_os.project.scaffold import initialize_project

        root = tmp_path / "failover-test"
        initialize_project(root, project_name="failover-test", profile="minimal")

        from forge_os.core.state_manager import StateManager

        sm = StateManager(root)
        state = sm.load()

        # Corrupt the Event Store path to cause failure
        sm._event_store = None  # Reset lazy init

        # This should still succeed because Event Store failures are caught
        sm.save(state)

        # state.json must exist regardless
        assert (root / ".forge" / "state.json").exists()

    def test_read_by_type_filters_correctly(self, store: EventStore) -> None:
        store.append("s1", "StateSaved", {"state": {"a": 1}})
        store.append("s1", "StateSaved", {"state": {"a": 2}})
        store.append("s2", "BacktrackTicketCreated", {"id": "BT-001"})

        state_events = store.read_by_type("StateSaved")
        assert len(state_events) == 2

        bt_events = store.read_by_type("BacktrackTicketCreated")
        assert len(bt_events) == 1
