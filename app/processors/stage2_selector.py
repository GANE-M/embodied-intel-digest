"""Stage-2 selection orchestration (shortlist, enrich, LLM judge, status machine)."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import AppConfig
from app.models import ProcessedItem
from app.processors.content_enricher import enrich_item_article, should_enrich_for_stage2
from app.processors.llm_judge import judge_item, stage2_sort_score

STAGE2_UNAVAILABLE = "stage2_unavailable"
STAGE2_FAILED = "stage2_failed"
STAGE2_SUCCESS_NONEMPTY = "stage2_success_nonempty"
STAGE2_SUCCESS_EMPTY = "stage2_success_empty"


def _compute_base_shortlist(candidates: list[ProcessedItem], config: AppConfig) -> list[ProcessedItem]:
    if config.top_n <= 0 or not candidates:
        return []
    mult = max(1, config.stage2_shortlist_multiplier)
    shortlist_cap = min(
        len(candidates),
        max(config.top_n * mult, config.top_n + 8),
    )
    return candidates[:shortlist_cap]


def _load_stage2_shortlist_rules(configs_dir: Path) -> dict:
    path = configs_dir / "stage2_shortlist_rules.json"
    if not path.is_file():
        return {
            "allowlist_enable": False,
            "entity_direct_allowlist": [],
            "source_name_direct_allowlist": [],
            "repo_direct_allowlist": [],
            "category_quota": {},
        }
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {
            "allowlist_enable": False,
            "entity_direct_allowlist": [],
            "source_name_direct_allowlist": [],
            "repo_direct_allowlist": [],
            "category_quota": {},
        }
    if not isinstance(data, dict):
        return {
            "allowlist_enable": False,
            "entity_direct_allowlist": [],
            "source_name_direct_allowlist": [],
            "repo_direct_allowlist": [],
            "category_quota": {},
        }
    return data


def _match_allowlist(item: ProcessedItem, rules: dict) -> bool:
    ent_allow = {str(x).strip().lower() for x in rules.get("entity_direct_allowlist", []) if str(x).strip()}
    src_allow = {str(x).strip().lower() for x in rules.get("source_name_direct_allowlist", []) if str(x).strip()}
    repo_allow = {str(x).strip().lower() for x in rules.get("repo_direct_allowlist", []) if str(x).strip()}

    if item.source_name.lower() in src_allow:
        return True
    if any(str(e).strip().lower() in ent_allow for e in item.matched_entities):
        return True
    repo = ""
    if isinstance(item.meta, dict):
        repo = str(item.meta.get("repo", "") or "").strip().lower()
    if repo and repo in repo_allow:
        return True
    return False


def build_stage2_shortlist(candidates: list[ProcessedItem], config: AppConfig) -> list[ProcessedItem]:
    """Build shortlist from stage1 head + optional allowlist pass-through (default off)."""
    base = _compute_base_shortlist(candidates, config)
    rules = _load_stage2_shortlist_rules(config.configs_dir)
    if not bool(rules.get("allowlist_enable", False)):
        return base

    selected = list(base)
    seen_ids = {id(x) for x in selected}
    for item in candidates:
        if id(item) in seen_ids:
            continue
        if _match_allowlist(item, rules):
            selected.append(item)
            seen_ids.add(id(item))
    return selected


def select_stage2_items(
    candidates: list[ProcessedItem],
    config: AppConfig,
    log,
) -> tuple[list[ProcessedItem], str, list[ProcessedItem]]:
    """Return selected items, stage2 status, and shortlist used for Stage-2 input."""
    if config.top_n <= 0:
        return [], STAGE2_SUCCESS_EMPTY, []

    stage1_ranked_items = candidates
    if not stage1_ranked_items:
        return [], STAGE2_SUCCESS_EMPTY, []

    shortlist = build_stage2_shortlist(stage1_ranked_items, config)

    api_key = (config.llm_api_key or "").strip()
    base_url = (config.llm_base_url or "").strip()
    if not api_key or not base_url:
        log.warning("stage2 unavailable: not enabled, fallback to stage1 top_n")
        return stage1_ranked_items[: config.top_n], STAGE2_UNAVAILABLE, shortlist

    try:
        for it in shortlist:
            if should_enrich_for_stage2(it):
                enrich_item_article(it, log=log)

        any_parsed = False
        for it in shortlist:
            j = judge_item(it, api_key=api_key, base_url=base_url)
            it.llm_judgement = j
            if j is not None:
                any_parsed = True
            else:
                log.warning("stage2 llm_judge missing/failed for %s", (it.title or "")[:120])

        if not any_parsed:
            log.warning("stage2 failed: no parsed judgements, fallback to stage1 top_n")
            return stage1_ranked_items[: config.top_n], STAGE2_FAILED, shortlist

        kept = [it for it in shortlist if it.llm_judgement and it.llm_judgement.keep]
        kept.sort(key=lambda x: (stage2_sort_score(x), x.final_score), reverse=True)
        if not kept:
            return [], STAGE2_SUCCESS_EMPTY, shortlist
        return kept[: config.top_n], STAGE2_SUCCESS_NONEMPTY, shortlist
    except Exception as exc:  # noqa: BLE001
        log.warning("stage2 failed with exception, fallback to stage1 top_n: %s", exc)
        return stage1_ranked_items[: config.top_n], STAGE2_FAILED, shortlist
