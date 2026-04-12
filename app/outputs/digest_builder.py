"""Plain-text digest only (v1.4). HTML lives in html_builder."""

from __future__ import annotations

import os
from collections.abc import Iterable

from app import constants
from app.models import ProcessedItem


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


def build_plaintext_digest(
    items: list[ProcessedItem],
    date_str: str,
    top_n: int,
) -> str:
    ranked = sorted(items, key=lambda x: digest_rank_key(x), reverse=True)[:top_n]
    hdr = (
        os.getenv("EMAIL_SUBJECT_PREFIX")
        or os.getenv("EMAIL_SUBJECT")
        or "Embodied Intel Digest"
    )
    lines = [
        f"{hdr} ({date_str})",
        "",
        f"Top {len(ranked)} items",
        "",
    ]
    grouped = group_items(ranked)
    for cat in sorted_category_names(grouped.keys()):
        lines.append(f"## {cat}")
        lines.append("")
        for it in grouped[cat]:
            flag = " [更新]" if it.is_update else ""
            lines.append(f"* {it.title}{flag}")
            lines.append(f"  {it.url}")
            note = ""
            if it.llm_judgement and it.llm_judgement.reason:
                note = f" | note: {it.llm_judgement.reason[:220]}"
            lines.append(f"  score={it.final_score:.3f} | {it.summary_zh[:200]}{note}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
