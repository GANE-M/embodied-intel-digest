"""Plain-text digest only (v1.4). HTML lives in html_builder."""

from __future__ import annotations

import os
from collections.abc import Iterable

from app import constants
from app.models import ProcessedItem
from app.outputs.render_context import build_digest_render_context


def digest_rank_key(item: ProcessedItem) -> tuple[float, float]:
    """Prefer Stage-2 composite when judgement exists; else Stage-1 final_score."""
    j = item.llm_judgement
    if j is not None:
        primary = (
            0.5 * j.brand_relevance_score
            + 0.3 * j.importance_score
            + 0.2 * j.novelty_score
        )
    else:
        primary = item.final_score
    return (primary, item.final_score)


def sorted_category_names(categories: Iterable[str]) -> list[str]:
    order = {c: i for i, c in enumerate(constants.CATEGORIES)}
    return sorted(categories, key=lambda c: order.get(c, len(constants.CATEGORIES)))


def group_items(items: list[ProcessedItem]) -> dict[str, list[ProcessedItem]]:
    groups: dict[str, list[ProcessedItem]] = {}
    for it in items:
        cat = it.category if it.category in constants.CATEGORIES else "media"
        groups.setdefault(cat, []).append(it)
    for key in groups:
        groups[key].sort(key=lambda x: digest_rank_key(x), reverse=True)
    return groups


def build_digest_subject(date_str: str) -> str:
    prefix = (
        os.getenv("EMAIL_SUBJECT_PREFIX")
        or os.getenv("EMAIL_SUBJECT")
        or "Embodied Intel Digest"
    )
    return f"{prefix} | {date_str}"


def _display_group_name(category: str) -> str:
    if category in ("company", "media"):
        return "News"
    if category == "research":
        return "Research"
    if category == "open_source":
        return "Open Source"
    if category == "event":
        return "Events"
    return category.title() if category else "News"


def build_plaintext_digest(
    items: list[ProcessedItem],
    date_str: str,
    top_n: int,
) -> str:
    ranked = sorted(items, key=lambda x: digest_rank_key(x), reverse=True)[:top_n]
    context = build_digest_render_context(ranked, date_str, top_n)
    groups: dict[str, list] = {}
    for entry, item in zip(context.entries, ranked, strict=False):
        groups.setdefault(item.category if item.category in constants.CATEGORIES else "media", []).append(entry)
    lines = [
        context.subject,
        "",
    ]
    for category in sorted_category_names(groups.keys()):
        lines.append(f"## {_display_group_name(category)}")
        lines.append("")
        for entry in groups[category]:
            title = f"{entry.title}{' [更新]' if entry.is_update else ''}"
            lines.append(f"Title: {title}")
            lines.append(f"URL: {entry.url}")
            lines.append(f"Tag: {entry.tag}")
            lines.append(f"EN: {entry.summary_en}")
            lines.append(f"ZH: {entry.summary_zh}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
