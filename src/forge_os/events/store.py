"""Phase 08.5 SQLite-backed append-only Event Store.

Dual-writes alongside state.json. state.json remains authoritative.
The Event Store provides replay, audit, and temporal query capabilities.

Schema:
    events:     append-only log (event_id PK AUTOINCREMENT)
    snapshots:  mutable checkpoint table for fast replay (stream_id PK)
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class EventStoreError(RuntimeError):
    """Raised when Event Store operations fail."""


class EventStore:
    """SQLite-backed append-only event log with snapshot support.

    WAL mode with synchronous=NORMAL for local-first dev tool workloads.
    Connection is lazy — created on first operation, not at __init__.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path.resolve()
        self._conn: sqlite3.Connection | None = None

    # ── Connection ───────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()
        return self._conn

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                stream_id   TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                payload     TEXT NOT NULL DEFAULT '{}',
                version     INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_stream
            ON events(stream_id, event_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type
            ON events(event_type, event_id)
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                stream_id       TEXT PRIMARY KEY,
                state           TEXT NOT NULL DEFAULT '{}',
                event_version   INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
        """)
        self._conn.commit()

    # ── Write ────────────────────────────────────────────────────────────

    def append(
        self,
        stream_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        """Append an event to the stream. Returns the new event_id."""
        conn = self._connect()
        payload_json = json.dumps(payload or {}, ensure_ascii=False)
        version = self._next_version(conn, stream_id)
        cursor = conn.execute(
            "INSERT INTO events (stream_id, event_type, payload, version) VALUES (?, ?, ?, ?)",
            (stream_id, event_type, payload_json, version),
        )
        conn.commit()
        event_id: int = cursor.lastrowid  # type: ignore[assignment]
        return event_id

    def append_state_event(
        self,
        stream_id: str,
        state: dict[str, Any],
    ) -> int:
        """Append a full-state-snapshot event. Used by dual-write."""
        return self.append(stream_id, "StateSaved", {"state": state})

    def save_snapshot(
        self,
        stream_id: str,
        state: dict[str, Any],
        event_version: int,
    ) -> None:
        """Upsert a snapshot for fast replay recovery."""
        conn = self._connect()
        state_json = json.dumps(state, ensure_ascii=False)
        conn.execute(
            "INSERT OR REPLACE INTO snapshots (stream_id, state, event_version) VALUES (?, ?, ?)",
            (stream_id, state_json, event_version),
        )
        conn.commit()

    # ── Read ─────────────────────────────────────────────────────────────

    def read_stream(self, stream_id: str) -> list[dict[str, Any]]:
        """Read all events for a stream, ordered by event_id."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT event_id, stream_id, event_type, payload, version, created_at "
            "FROM events WHERE stream_id = ? ORDER BY event_id",
            (stream_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def read_stream_from(
        self,
        stream_id: str,
        from_version: int,
    ) -> list[dict[str, Any]]:
        """Read events from a specific version onwards."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT event_id, stream_id, event_type, payload, version, created_at "
            "FROM events WHERE stream_id = ? AND version > ? ORDER BY event_id",
            (stream_id, from_version),
        ).fetchall()
        return [dict(r) for r in rows]

    def read_all(self) -> list[dict[str, Any]]:
        """Read all events across all streams in global order."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT event_id, stream_id, event_type, payload, version, created_at "
            "FROM events ORDER BY event_id"
        ).fetchall()
        return [dict(r) for r in rows]

    def read_by_type(self, event_type: str) -> list[dict[str, Any]]:
        """Read all events of a given type."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT event_id, stream_id, event_type, payload, version, created_at "
            "FROM events WHERE event_type = ? ORDER BY event_id",
            (event_type,),
        ).fetchall()
        return [dict(r) for r in rows]

    def load_snapshot(self, stream_id: str) -> dict[str, Any] | None:
        """Load the latest snapshot for a stream."""
        conn = self._connect()
        row = conn.execute(
            "SELECT state, event_version, created_at "
            "FROM snapshots WHERE stream_id = ?",
            (stream_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "stream_id": stream_id,
            "state": json.loads(row["state"]),
            "event_version": row["event_version"],
            "created_at": row["created_at"],
        }

    # ── Replay ───────────────────────────────────────────────────────────

    def replay(self, stream_id: str) -> list[dict[str, Any]]:
        """Replay all events for a stream, returning the full event log.

        For state reconstruction, use replay_state() which applies
        events incrementally from the latest snapshot.
        """
        return self.read_stream(stream_id)

    def replay_state(self, stream_id: str) -> dict[str, Any] | None:
        """Reconstruct current state by applying events from last snapshot.

        Returns None if no events exist for this stream.
        """
        snapshot = self.load_snapshot(stream_id)
        events = self.read_stream(stream_id)
        if not events:
            return None

        state: dict[str, Any] = {}
        start_version = 0

        if snapshot is not None:
            state = dict(snapshot["state"])
            start_version = snapshot["event_version"]

        for event in events:
            if event["version"] <= start_version:
                continue
            payload = json.loads(event["payload"])
            if "state" in payload:
                state.update(payload["state"])

        return state

    # ── Lifecycle ────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    def __enter__(self) -> EventStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ── Private ──────────────────────────────────────────────────────────

    @staticmethod
    def _next_version(conn: sqlite3.Connection, stream_id: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS next_version "
            "FROM events WHERE stream_id = ?",
            (stream_id,),
        ).fetchone()
        return row["next_version"] if row else 1
