"""Stage-1 candidate selection with allowlist / priority routing."""

from __future__ import annotations

import re

from app.config import AppConfig
from app.models import ProcessedItem


_SHORT_HINTS = {"vla"}


def _norm(value: str) -> str:
    return (value or "").strip().lower()


def _repo_name(item: ProcessedItem) -> str:
    if isinstance(item.meta, dict):
        return _norm(str(item.meta.get("repo_name", "") or ""))
    return ""


def _title_prefix_repo(item: ProcessedItem) -> str:
    title = (item.title or "").strip()
    if title.startswith("[") and "]" in title:
        return _norm(title[1 : title.index("]")])
    return ""


def _allowlist_repo_match(item: ProcessedItem, allowlist: list[str]) -> bool:
    repo = _repo_name(item)
    title_repo = _title_prefix_repo(item)
    for raw in allowlist:
        target = _norm(raw)
        if not target:
            continue
        if repo == target or title_repo == target:
            return True
    return False


def _topic_hint_hit(text: str, hints: list[str]) -> bool:
    hay = _norm(text)
    for raw in hints:
        hint = _norm(raw)
        if not hint:
            continue
        if hint in _SHORT_HINTS:
            if re.search(rf"\b{re.escape(hint)}\b", hay):
                return True
            continue
        if hint in hay:
            return True
    return False


def _matched_topic_hint(item: ProcessedItem, config: AppConfig) -> bool:
    rules = config.filter_rules.priority_source_topic_hints
    source_name = _norm(item.source_name)
    if source_name in rules:
        text = " ".join([item.title or "", item.text or "", item.url or ""])
        return _topic_hint_hit(text, rules[source_name])
    return False


def _passes_hard_filters(item: ProcessedItem, rules) -> bool:
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

    return True


def _item_has_core_signal(item: ProcessedItem) -> bool:
    return bool(item.matched_keywords or item.matched_entities)


def select_stage1_candidates(
    new_items: list[ProcessedItem],
    config: AppConfig,
) -> list[ProcessedItem]:
    rules = config.filter_rules
    priority_source_names = {_norm(x) for x in rules.priority_sources}
    absolute: list[ProcessedItem] = []
    priority: list[ProcessedItem] = []
    regular: list[ProcessedItem] = []

    for item in new_items:
        if not _passes_hard_filters(item, rules):
            continue

        if _allowlist_repo_match(item, rules.absolute_allowlist):
            absolute.append(item)
            continue

        if _norm(item.source_name) in priority_source_names:
            if item.matched_keywords or _matched_topic_hint(item, config):
                priority.append(item)
            continue

        if item.final_score >= config.min_final_score and _item_has_core_signal(item):
            regular.append(item)

    absolute.sort(key=lambda x: x.final_score, reverse=True)
    priority.sort(key=lambda x: x.final_score, reverse=True)
    regular.sort(key=lambda x: x.final_score, reverse=True)
    return absolute + priority + regular
