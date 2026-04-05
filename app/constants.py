"""Global enums and defaults (v1.4 — single source of truth)."""

from __future__ import annotations

SOURCE_TYPES: tuple[str, ...] = (
    "arxiv",
    "github",
    "rss",
    "company",
    "event",
    "openalex",
)

CATEGORIES: tuple[str, ...] = (
    "research",
    "open_source",
    "company",
    "media",
    "event",
)

SUMMARY_MODES: tuple[str, ...] = ("template", "llm")

RUN_STATUS_SUCCESS: str = "success"
RUN_STATUS_PARTIAL: str = "partial_success"
RUN_STATUS_FAILED: str = "failed"
RUN_STATUSES: tuple[str, ...] = (
    RUN_STATUS_SUCCESS,
    RUN_STATUS_PARTIAL,
    RUN_STATUS_FAILED,
)

STORE_TYPES_JSON: str = "json"
STORE_TYPES_UNSUPPORTED: tuple[str, ...] = ("sqlite", "postgres", "supabase")

DEFAULT_TOP_N: int = 20
DEFAULT_LOOKBACK_HOURS: int = 24
DEFAULT_SUMMARY_MODE: str = "template"

DEFAULT_SOURCE_WEIGHTS: dict[str, float] = {
    "arxiv": 1.0,
    "openalex": 1.0,
    "github": 0.95,
    "rss": 0.85,
    "company": 0.9,
    "event": 0.8,
}

DEFAULT_KEYWORD_WEIGHT: float = 0.35
DEFAULT_ENTITY_WEIGHT: float = 0.25
DEFAULT_FRESHNESS_WEIGHT: float = 0.25
DEFAULT_SOURCE_SCORE_WEIGHT: float = 0.15
