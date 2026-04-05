"""Hashing helpers for dedupe and stable IDs (supplemental v1.1)."""

from __future__ import annotations

import hashlib


def normalize_for_hash(text: str) -> str:
    """Collapse internal whitespace, lowercase, strip ends (for fingerprint input)."""
    return " ".join((text or "").lower().split())


def make_hash(text: str) -> str:
    """Return SHA-256 hex digest of UTF-8 ``normalize_for_hash(text)``."""
    payload = normalize_for_hash(text)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_dedupe_id(
    source_type: str,
    source_name: str,
    external_id: str,
    title: str,
    url: str,
) -> str:
    """Build a dedupe fingerprint from five normalized fields (newline-joined, then SHA-256)."""
    line = "\n".join(
        normalize_for_hash(x) for x in (source_type, source_name, external_id, title, url)
    )
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def build_canonical_id(title: str, authors: list[str] | None = None) -> str:
    """Stable id from title and optional author list (for clustering, not arXiv ids)."""
    parts = [normalize_for_hash(title)]
    if authors:
        parts.append(normalize_for_hash(", ".join(authors)))
    return make_hash("\n".join(parts))


def stable_hash(*parts: str) -> str:
    """Join parts with newlines and SHA-256 the UTF-8 payload (legacy helper)."""
    payload = "\n".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_dedupe_id(source: str, external_id: str, url: str, title: str) -> str:
    """Legacy four-field dedupe id used across sources (unchanged semantics)."""
    return stable_hash(source.strip().lower(), external_id.strip(), url.strip(), title.strip())


def hash_text(text: str) -> str:
    """SHA-256 hex of raw ``text`` UTF-8 (no normalization)."""
    return stable_hash(text)
