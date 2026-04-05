"""Clean RawItem text fields; delegate primitives to text_utils (v1.4)."""

from __future__ import annotations

from copy import deepcopy

from app.models import RawItem
from app.utils.text_utils import (
    normalize_unicode,
    normalize_whitespace,
    safe_truncate,
    strip_html,
)


def clean_raw_item(item: RawItem) -> RawItem:
    meta = deepcopy(item.meta) if item.meta else {}
    title = normalize_whitespace(strip_html(normalize_unicode(item.title)))
    text = normalize_whitespace(strip_html(normalize_unicode(item.text)))
    raw_c = item.raw_content
    if raw_c is not None:
        raw_c = normalize_whitespace(strip_html(normalize_unicode(raw_c)))
        raw_c = safe_truncate(raw_c, 50_000)
    return RawItem(
        source_type=item.source_type,
        source_name=item.source_name,
        external_id=item.external_id,
        dedupe_id=item.dedupe_id,
        canonical_id=item.canonical_id,
        title=title,
        text=text,
        raw_content=raw_c,
        url=item.url.strip(),
        published_at=item.published_at,
        updated_at=item.updated_at,
        authors=[normalize_whitespace(normalize_unicode(a)) for a in item.authors],
        tags=[normalize_whitespace(normalize_unicode(t)) for t in item.tags],
        meta=meta,
    )
