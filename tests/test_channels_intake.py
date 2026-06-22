"""Tests for channel feedback intake: dedup + rate limit (FR-CH-002, P11.05/07)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from forge_os.channels.errors import ChannelDuplicateError, ChannelRateLimitError
from forge_os.channels.intake import FeedbackQueue
from forge_os.schemas.channel import FeedbackItem


def _item(sender="alice", text="please fix", created_at=None) -> FeedbackItem:
    fields = {"channel_id": "console", "sender": sender, "text": text}
    if created_at is not None:
        fields["created_at"] = created_at
    return FeedbackItem(**fields)


def test_empty_queue(tmp_path):
    assert FeedbackQueue(tmp_path).list_pending() == []


def test_submit_then_list(tmp_path):
    queue = FeedbackQueue(tmp_path)
    queue.submit(_item())
    pending = queue.list_pending()
    assert len(pending) == 1
    assert pending[0].sender == "alice"


def test_duplicate_rejected(tmp_path):
    queue = FeedbackQueue(tmp_path)
    queue.submit(_item(text="same"))
    with pytest.raises(ChannelDuplicateError):
        queue.submit(_item(text="same"))


def test_rate_limit_enforced(tmp_path):
    queue = FeedbackQueue(tmp_path, max_per_window=3, window_seconds=60.0)
    now = datetime(2026, 6, 22, 12, 0, 0)
    for index in range(3):
        queue.submit(_item(text=f"item-{index}", created_at=now.isoformat()), now=now)
    with pytest.raises(ChannelRateLimitError):
        queue.submit(_item(text="item-4", created_at=now.isoformat()), now=now)


def test_rate_limit_resets_after_window(tmp_path):
    queue = FeedbackQueue(tmp_path, max_per_window=2, window_seconds=60.0)
    old = datetime(2026, 6, 22, 12, 0, 0)
    for index in range(2):
        queue.submit(_item(text=f"old-{index}", created_at=old.isoformat()), now=old)
    later = old + timedelta(seconds=120)
    queue.submit(_item(text="fresh", created_at=later.isoformat()), now=later)
    assert len(queue.list_pending()) == 3


def test_feedback_isolated_under_forge_dir(tmp_path):
    FeedbackQueue(tmp_path).submit(_item())
    assert (tmp_path / ".forge" / "channels" / "feedback.jsonl").exists()


def test_rate_limit_tolerates_timezone_mismatch(tmp_path):
    # A naive/aware mismatch in the window check must fail safe, not crash intake.
    queue = FeedbackQueue(tmp_path, max_per_window=2, window_seconds=60.0)
    aware = datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC)
    queue.submit(_item(text="aware", created_at=aware.isoformat()), now=aware)
    queue.submit(_item(text="naive"), now=datetime(2026, 6, 22, 12, 0, 30))
    assert len(queue.list_pending()) == 2
