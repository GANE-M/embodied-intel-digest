"""Scorer tests: 0.0–1.0 normalization and final_score (v1.4)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import KeywordRule, RawItem, ScoringConfig, TrackedEntity
from app.processors.scorer import (
    compute_freshness_score,
    compute_keyword_score,
    compute_source_score,
    score_item,
)


def test_compute_keyword_score_range() -> None:
    text = "Humanoid robots for embodied ai research"
    rules = [
        KeywordRule(pattern="humanoid", match_type="literal", weight=0.5),
        KeywordRule(pattern="embodied ai", match_type="literal", weight=0.5),
        KeywordRule(pattern="unused", match_type="literal", weight=0.2),
    ]
    score, hits = compute_keyword_score(text, rules)
    assert 0.0 <= score <= 1.0
    assert "humanoid" in hits and "embodied ai" in hits


def test_compute_freshness_score() -> None:
    now = datetime.now(timezone.utc)
    recent = compute_freshness_score(now, now)
    old = compute_freshness_score(now - timedelta(days=14), now)
    assert recent > old
    assert 0.0 <= recent <= 1.0


def test_compute_source_score_clamped() -> None:
    sc = ScoringConfig(source_weights={"arxiv": 1.0})
    raw = RawItem(
        source_type="arxiv",
        source_name="x",
        external_id="e",
        dedupe_id="d",
        canonical_id=None,
        title="t",
        text="",
        raw_content=None,
        url="",
        published_at=datetime.now(timezone.utc),
        updated_at=None,
        meta={},
    )
    assert compute_source_score(raw, sc) == 1.0
    raw_prio = RawItem(
        source_type="arxiv",
        source_name="x",
        external_id="e2",
        dedupe_id="d2",
        canonical_id=None,
        title="t",
        text="",
        raw_content=None,
        url="",
        published_at=datetime.now(timezone.utc),
        updated_at=None,
        meta={"source_priority": 0.42},
    )
    assert abs(compute_source_score(raw_prio, sc) - 0.42) < 1e-9


def test_score_item_final_in_unit_interval() -> None:
    raw = RawItem(
        source_type="arxiv",
        source_name="arXiv",
        external_id="e1",
        dedupe_id="d1",
        canonical_id="1234.5678",
        title="Humanoid control",
        text="Embodied ai and humanoid locomotion.",
        raw_content=None,
        url="https://example.com/p1",
        published_at=datetime.now(timezone.utc),
        updated_at=None,
        meta={},
    )
    rules = [KeywordRule(pattern="humanoid", match_type="literal", weight=1.0)]
    entities: list[TrackedEntity] = []
    sc = ScoringConfig(
        source_weights={"arxiv": 1.0},
        keyword_weight=0.35,
        entity_weight=0.25,
        freshness_weight=0.25,
        source_weight=0.15,
    )
    now = datetime.now(timezone.utc)
    proc = score_item(raw, rules, entities, sc, now)
    assert 0.0 <= proc.keyword_score <= 1.0
    assert 0.0 <= proc.final_score <= 1.0
