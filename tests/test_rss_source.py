"""RSSSource: meta + timezone-aware datetimes (mocked network)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.sources.rss_source import RSSSource


def test_rss_entry_meta_and_timezone() -> None:
    feed = {
        "name": "Test Feed",
        "url": "https://example.com/feed.xml",
        "category": "research",
        "priority": 0.91,
        "enabled": True,
    }
    entry = SimpleNamespace(
        title="Hello",
        summary="World",
        description="",
        link="https://example.com/p/1",
        id="id1",
        published_parsed=(2026, 4, 1, 12, 0, 0, 0, 0, 0),
        updated_parsed=None,
        authors=[],
    )
    parsed = SimpleNamespace(entries=[entry])
    src = RSSSource([feed])
    since = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with patch("app.sources.rss_source.feedparser.parse", return_value=parsed):
        items = src.fetch(since)
    assert len(items) == 1
    it = items[0]
    assert it.meta.get("feed_name") == "Test Feed"
    assert it.meta.get("source_priority") == 0.91
    assert it.meta.get("source_category") == "research"
    assert it.published_at.tzinfo is not None
