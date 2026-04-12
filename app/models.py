"""Canonical datatypes for Embodied Intel Digest (v1.4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class KeywordRule:
    """Single keyword / regex rule from tracked_keywords.json."""

    pattern: str
    match_type: str = "literal"
    weight: float = 1.0
    case_sensitive: bool = False
    category_hint: str = ""


@dataclass
class TrackedEntity:
    """Entity row from tracked_entities.json (JSON key ``type`` / ``entity_type``)."""

    name: str
    aliases: list[str] = field(default_factory=list)
    entity_type: str = ""
    priority: float = 1.0
    source_preference: list[str] = field(default_factory=list)


@dataclass
class DeliveryTarget:
    """One SMTP endpoint + recipient list (multi-server digest delivery)."""

    name: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    email_from: str
    email_to: list[str]
    use_ssl: bool = False
    enabled: bool = True


@dataclass
class ScoringConfig:
    """Weights for sub-scores and final_score (typically sum to 1.0)."""

    source_weights: dict[str, float]
    keyword_weight: float = 0.35
    entity_weight: float = 0.25
    freshness_weight: float = 0.25
    source_weight: float = 0.15


@dataclass
class RunMetadata:
    run_id: str
    started_at: datetime
    finished_at: datetime
    status: str
    item_count: int
    error_count: int


@dataclass
class JudgementResult:
    """Stage-2 LLM structured judgement (internal contract, not the digest body)."""

    keep: bool
    importance_score: float
    novelty_score: float
    brand_relevance_score: float
    reason: str
    content_type: str


@dataclass
class FilterRules:
    """Stage-1 hard filters loaded from ``configs/filter_rules.json``."""

    title_blocklist: list[str] = field(default_factory=list)
    url_blocklist: list[str] = field(default_factory=list)
    source_blocklist: list[str] = field(default_factory=list)
    source_allowlist: list[str] = field(default_factory=list)


@dataclass
class RawItem:
    source_type: str
    source_name: str
    external_id: str
    dedupe_id: str
    canonical_id: str | None
    title: str
    text: str
    raw_content: str | None
    url: str
    published_at: datetime
    updated_at: datetime | None
    authors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessedItem(RawItem):
    category: str = ""
    matched_keywords: list[str] = field(default_factory=list)
    matched_entities: list[str] = field(default_factory=list)
    keyword_score: float = 0.0
    entity_score: float = 0.0
    freshness_score: float = 0.0
    source_score: float = 0.0
    final_score: float = 0.0
    summary_zh: str = ""
    is_update: bool = False
    llm_judgement: JudgementResult | None = None
