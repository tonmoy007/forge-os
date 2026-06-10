"""Tests for the shared Dreamer timestamp parser."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from forge_os.dreamer.timeutil import parse_timestamp


def test_parses_z_suffixed_utc_timestamp() -> None:
    parsed = parse_timestamp("2026-06-10T12:00:00Z")

    assert parsed == datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def test_parses_explicit_offset_timestamp() -> None:
    parsed = parse_timestamp("2026-06-10T12:00:00+00:00")

    assert parsed == datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def test_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_timestamp("not-a-timestamp")
