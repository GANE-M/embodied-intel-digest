"""Scoring with models.KeywordRule / models.TrackedEntity (v1.4).

``KeywordRule.category_hint`` is loaded from JSON for future routing; it does not
affect scores in this version.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app import constants
from app.models import KeywordRule, ProcessedItem, RawItem, ScoringConfig, TrackedEntity
from app.utils.text_utils import normalize_whitespace


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _regex_match(text: str, pattern: str, case_sensitive: bool) -> bool:
    hay = normalize_whitespace(text)
    try:
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.search(pattern, hay, flags=flags) is not None
    except re.error:
        return False


def _literal_match(text: str, pattern: str, case_sensitive: bool) -> bool:
    pat = pattern.strip()
    if not pat:
        return False
    hay_raw = normalize_whitespace(text)
    hay_lower = hay_raw.lower()
    subj_lower = pat.lower()
    if len(subj_lower) <= 3:
        if case_sensitive:
            return (
                re.search(
                    rf"(?<![A-Za-z0-9]){re.escape(pat)}(?![A-Za-z0-9])",
                    hay_raw,
                )
                is not None
            )
        return (
            re.search(
                rf"(?<![a-z0-9]){re.escape(subj_lower)}(?![a-z0-9])",
                hay_lower,
            )
            is not None
        )
    if case_sensitive:
        return pat in hay_raw
    return subj_lower in hay_lower


def _entity_term_in_hay(hay_lower: str, term: str) -> bool:
    t = term.strip().lower()
    if not t:
        return False
    if len(t) <= 3:
        return (
            re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", hay_lower) is not None
        )
    return t in hay_lower


def compute_keyword_score(
    text: str,
    keyword_rules: list[KeywordRule],
) -> tuple[float, list[str]]:
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
        if mt == "regex":
            hit = _regex_match(text, pattern, rule.case_sensitive)
        else:
            hit = _literal_match(text, pattern, rule.case_sensitive)
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
        terms = [name]
        for a in ent.aliases:
            if a.strip():
                terms.append(a.strip())
        hit = any(_entity_term_in_hay(hay, t) for t in terms)
        if hit:
            matched.append(name)
            raw += priority
    denom = max_total if max_total > 0 else 1.0
    return _clamp01(raw / denom), matched


def compute_freshness_score(
    published_at: datetime,
    current_time: datetime,
    primary_window_hours: float,
) -> float:
    now = current_time
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    pub = published_at
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    else:
        pub = pub.astimezone(timezone.utc)
    primary_window_hours = max(1.0, float(primary_window_hours))
    delta_hours = max(0.0, (now - pub).total_seconds() / 3600.0)
    grace_window_end_hours = 2.0 * primary_window_hours
    if delta_hours <= primary_window_hours:
        return 0.30
    if delta_hours <= grace_window_end_hours:
        span = grace_window_end_hours - primary_window_hours
        if span <= 0:
            return 0.0
        ratio = (delta_hours - primary_window_hours) / span
        return _clamp01(0.15 * (1.0 - ratio))
    return 0.0


def compute_time_bucket(
    published_at: datetime,
    current_time: datetime,
    primary_window_hours: float,
) -> str:
    now = current_time
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    pub = published_at
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    else:
        pub = pub.astimezone(timezone.utc)
    primary_window_hours = max(1.0, float(primary_window_hours))
    delta_hours = max(0.0, (now - pub).total_seconds() / 3600.0)
    if delta_hours <= 2.0 * primary_window_hours:
        return "primary_window" if delta_hours <= primary_window_hours else "grace_window"
    return "grace_window"


def compute_source_score(
    raw_item: RawItem,
    scoring_config: ScoringConfig,
) -> float:
    meta = raw_item.meta or {}
    sp = meta.get("source_priority")
    if sp is not None and sp != "":
        try:
            return _clamp01(float(sp))
        except (TypeError, ValueError):
            pass
    st = (raw_item.source_type or "").lower()
    w = scoring_config.source_weights.get(st, 0.75)
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
    primary_window_hours = float(getattr(scoring_config, "primary_window_hours", constants.DEFAULT_LOOKBACK_HOURS))
    fresh = compute_freshness_score(raw_item.published_at, current_time, primary_window_hours)
    src = compute_source_score(raw_item, scoring_config)
    wk = scoring_config.keyword_weight
    we = scoring_config.entity_weight
    wf = scoring_config.freshness_weight
    ws = scoring_config.source_weight
    final = wk * kw_score + we * ent_score + wf * fresh + ws * src
    meta = dict(raw_item.meta or {})
    meta.setdefault(
        "time_bucket",
        compute_time_bucket(raw_item.published_at, current_time, primary_window_hours),
    )
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
        meta=meta,
        category="",
        matched_keywords=kw_hits,
        matched_entities=ent_hits,
        keyword_score=kw_score,
        entity_score=ent_score,
        freshness_score=fresh,
        source_score=src,
        final_score=_clamp01(final),
        summary_en="",
        summary_zh="",
        is_update=False,
    )
