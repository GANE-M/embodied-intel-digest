"""Deduper: dedupe_id priority, URL/title fallback, unseen filter (v1.4)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models import ProcessedItem
from app.processors.deduper import build_dedupe_key, dedupe_items, filter_unseen_items
from app.storage.memory_store import MemoryStore


def _item(
    *,
    url: str,
    title: str,
    score: float,
    dedupe_id: str,
    ext: str = "x",
) -> ProcessedItem:
    return ProcessedItem(
        source_type="rss",
        source_name="feed",
        external_id=ext,
        dedupe_id=dedupe_id,
        canonical_id=None,
        title=title,
        text="",
        raw_content=None,
        url=url,
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=None,
        final_score=score,
    )


def test_build_dedupe_key_prefers_dedupe_id() -> None:
    a = _item(url="https://a.test/x", title="t1", score=1.0, dedupe_id="same")
    b = _item(url="https://other", title="different", score=2.0, dedupe_id="same")
    assert build_dedupe_key(a) == build_dedupe_key(b)


def test_build_dedupe_key_url_title_fallback() -> None:
    p = ProcessedItem(
        source_type="rss",
        source_name="f",
        external_id="e",
        dedupe_id="",
        canonical_id=None,
        title="Hello",
        text="",
        raw_content=None,
        url="https://u.test/1",
        published_at=datetime.now(timezone.utc),
        updated_at=None,
    )
    q = ProcessedItem(
        source_type="rss",
        source_name="f",
        external_id="e2",
        dedupe_id="",
        canonical_id=None,
        title="Hello",
        text="",
        raw_content=None,
        url="https://u.test/1",
        published_at=datetime.now(timezone.utc),
        updated_at=None,
    )
    assert build_dedupe_key(p) == build_dedupe_key(q)


def test_dedupe_items_keeps_highest_score() -> None:
    hi = _item(url="https://dup.test/1", title="hi", score=0.9, dedupe_id="dup")
    lo = _item(url="https://dup.test/1", title="lo", score=0.1, dedupe_id="dup")
    other = _item(url="https://other.test/2", title="o", score=0.5, dedupe_id="o")
    out = dedupe_items([hi, lo, other])
    assert len(out) == 2
    dup = next(x for x in out if x.dedupe_id == "dup")
    assert dup.title == "hi"


def test_filter_unseen_uses_store_only() -> None:
    store = MemoryStore()
    a = _item(url="u1", title="a", score=1.0, dedupe_id="a")
    b = _item(url="u2", title="b", score=0.5, dedupe_id="b")
    store.mark_seen([a])
    unseen = filter_unseen_items([a, b], store)
    assert len(unseen) == 1
    assert unseen[0].dedupe_id == "b"
