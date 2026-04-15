"""Display-layer digest context for text/HTML/template rendering."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.models import ProcessedItem


_REJECT_TAG_CHARS = ("\\", "[", "]", "(", ")", "+", "?", "|", "^", "$", "*")


@dataclass
class DigestEntryViewModel:
    title: str
    url: str
    tag: str
    summary_en: str
    summary_zh: str
    is_update: bool


@dataclass
class DigestRenderContext:
    subject: str
    date_str: str
    top_n: int
    entries: list[DigestEntryViewModel]


def _is_human_readable_keyword(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    return not any(ch in s for ch in _REJECT_TAG_CHARS)


def _derive_tag(item: ProcessedItem) -> str:
    readable_keywords = [kw for kw in item.matched_keywords if _is_human_readable_keyword(kw)]
    if readable_keywords:
        return ", ".join(readable_keywords[:3])
    if item.matched_entities:
        return ", ".join(item.matched_entities[:2])
    if getattr(item, "tags", None):
        first = str(item.tags[0] or "").strip()
        if first:
            return first
    return item.category or "media"


def build_digest_render_context(items: list[ProcessedItem], date_str: str, top_n: int) -> DigestRenderContext:
    entries: list[DigestEntryViewModel] = []
    for item in items[:top_n]:
        entries.append(
            DigestEntryViewModel(
                title=item.title,
                url=item.url,
                tag=_derive_tag(item),
                summary_en=item.summary_en or "",
                summary_zh=item.summary_zh or "",
                is_update=bool(item.is_update),
            ),
        )
    subject = f"Embodied Intel Digest | {date_str}"
    return DigestRenderContext(subject=subject, date_str=date_str, top_n=top_n, entries=entries)
