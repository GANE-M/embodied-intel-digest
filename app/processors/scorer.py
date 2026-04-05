"""Scoring with models.KeywordRule / models.TrackedEntity (v1.4)."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from app.models import KeywordRule, ProcessedItem, RawItem, ScoringConfig, TrackedEntity
from app.utils.text_utils import normalize_whitespace


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def compute_keyword_score(
    text: str,
    keyword_rules: list[KeywordRule],
) -> tuple[float, list[str]]:
    hay = normalize_whitespace(text).lower()
    matched: list[str] = []
    raw = 0.0
    max_total = 0.0
    for rule in keyword_rules:
        pattern = (rule.pattern or "").strip()
        if not pattern:
            continue
        weight = max(0.0, float(rule.weight))
        max_total += weight
        mt = (rule.match_type or "literal").lower()
        hit = False
        if mt == "regex":
            try:
                hit = re.search(pattern, hay, flags=re.IGNORECASE) is not None
            except re.error:
                hit = False
        else:
            hit = pattern.lower() in hay
        if hit:
            matched.append(pattern)
            raw += weight
    denom = max_total if max_total > 0 else 1.0
    return _clamp01(raw / denom), matched


def compute_entity_score(
    text: str,
    entities: list[TrackedEntity],
) -> tuple[float, list[str]]:
    hay = normalize_whitespace(text).lower()
    matched: list[str] = []
    raw = 0.0
    max_total = 0.0
    for ent in entities:
        name = (ent.name or "").strip()
        if not name:
            continue
        priority = max(0.0, float(ent.priority))
        max_total += priority
        names = [name.lower()]
        for a in ent.aliases:
            if a.strip():
                names.append(a.strip().lower())
        hit = any(n and n in hay for n in names)
        if hit:
            matched.append(name)
            raw += priority
    denom = max_total if max_total > 0 else 1.0
    return _clamp01(raw / denom), matched


def compute_freshness_score(published_at: datetime, current_time: datetime) -> float:
    now = current_time
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    pub = published_at
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    else:
        pub = pub.astimezone(timezone.utc)
    delta_hours = max(0.0, (now - pub).total_seconds() / 3600.0)
    half_life = 48.0
    return _clamp01(math.exp(-delta_hours / half_life))


def compute_source_score(
    source_type: str,
    source_name: str,
    scoring_config: ScoringConfig,
) -> float:
    _ = source_name
    w = scoring_config.source_weights.get(source_type.lower(), 0.75)
    return _clamp01(w)


def score_item(
    raw_item: RawItem,
    keyword_rules: list[KeywordRule],
    entities: list[TrackedEntity],
    scoring_config: ScoringConfig,
    current_time: datetime,
) -> ProcessedItem:
    blob = f"{raw_item.title}\n{raw_item.text}"
    kw_score, kw_hits = compute_keyword_score(blob, keyword_rules)
    ent_score, ent_hits = compute_entity_score(blob, entities)
    fresh = compute_freshness_score(raw_item.published_at, current_time)
    src = compute_source_score(
        raw_item.source_type,
        raw_item.source_name,
        scoring_config,
    )
    wk = scoring_config.keyword_weight
    we = scoring_config.entity_weight
    wf = scoring_config.freshness_weight
    ws = scoring_config.source_weight
    final = wk * kw_score + we * ent_score + wf * fresh + ws * src
    return ProcessedItem(
        source_type=raw_item.source_type,
        source_name=raw_item.source_name,
        external_id=raw_item.external_id,
        dedupe_id=raw_item.dedupe_id,
        canonical_id=raw_item.canonical_id,
        title=raw_item.title,
        text=raw_item.text,
        raw_content=raw_item.raw_content,
        url=raw_item.url,
        published_at=raw_item.published_at,
        updated_at=raw_item.updated_at,
        authors=raw_item.authors,
        tags=raw_item.tags,
        meta=raw_item.meta,
        category="",
        matched_keywords=kw_hits,
        matched_entities=ent_hits,
        keyword_score=kw_score,
        entity_score=ent_score,
        freshness_score=fresh,
        source_score=src,
        final_score=_clamp01(final),
        summary_zh="",
        is_update=False,
    )
