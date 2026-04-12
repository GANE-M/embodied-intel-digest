"""Stage-1 hard filters from ``filter_rules.json`` (v3 upgrade)."""

from __future__ import annotations

from app.models import FilterRules, ProcessedItem


def passes_stage1_filters(item: ProcessedItem, rules: FilterRules) -> bool:
    """Return False if the item should be dropped before shortlist / Stage 2."""
    title = (item.title or "").lower()
    url = (item.url or "").lower()
    st = (item.source_type or "").lower()
    sn = (item.source_name or "").lower()

    for phrase in rules.title_blocklist:
        p = (phrase or "").lower()
        if p and p in title:
            return False

    for phrase in rules.url_blocklist:
        p = (phrase or "").lower()
        if p and p in url:
            return False

    for phrase in rules.source_blocklist:
        p = (phrase or "").lower()
        if not p:
            continue
        if p == st or p in sn:
            return False

    if rules.source_allowlist:
        allowed = False
        for phrase in rules.source_allowlist:
            p = (phrase or "").lower()
            if not p:
                continue
            if p == st or p in sn:
                allowed = True
                break
        if not allowed:
            return False

    return True
