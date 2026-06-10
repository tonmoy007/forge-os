"""Shared timestamp parsing for Dreamer modules."""

from __future__ import annotations

from datetime import datetime


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, accepting the project's `Z` suffix."""

    return datetime.fromisoformat(value.replace("Z", "+00:00"))
