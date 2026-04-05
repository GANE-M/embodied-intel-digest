"""Digest builder: subject, grouping order, plaintext (v1.4)."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from app import constants
from app.models import ProcessedItem
from app.outputs.digest_builder import (
    build_digest_subject,
    build_plaintext_digest,
    group_items,
    sorted_category_names,
)


def _proc(title: str, cat: str, score: float) -> ProcessedItem:
    return ProcessedItem(
        source_type="rss",
        source_name="f",
        external_id=title,
        dedupe_id=f"id-{title}",
        canonical_id=None,
        title=title,
        text="body",
        raw_content=None,
        url=f"https://example.com/{title}",
        published_at=datetime.now(timezone.utc),
        updated_at=None,
        category=cat,
        final_score=score,
        summary_zh="摘要",
    )


def test_sorted_category_names_follows_constants_order() -> None:
    keys = {"media", "research", "company"}
    ordered = sorted_category_names(keys)
    indices = [constants.CATEGORIES.index(k) for k in ordered]
    assert indices == sorted(indices)


def test_group_items() -> None:
    items = [_proc("a", "research", 0.5), _proc("b", "research", 0.9), _proc("c", "media", 0.3)]
    g = group_items(items)
    assert set(g.keys()) <= set(constants.CATEGORIES)
    assert g["research"][0].title == "b"


def test_build_digest_subject() -> None:
    old = os.environ.get("EMAIL_SUBJECT_PREFIX")
    os.environ["EMAIL_SUBJECT_PREFIX"] = "Test Prefix"
    try:
        sub = build_digest_subject("2026-04-04")
        assert "Test Prefix" in sub
        assert "2026-04-04" in sub
    finally:
        if old is None:
            os.environ.pop("EMAIL_SUBJECT_PREFIX", None)
        else:
            os.environ["EMAIL_SUBJECT_PREFIX"] = old


def test_build_plaintext_digest() -> None:
    items = [_proc("top", "research", 1.0), _proc("mid", "research", 0.5)]
    text = build_plaintext_digest(items, "2026-04-04", top_n=10)
    assert "top" in text
    assert "https://example.com/top" in text
