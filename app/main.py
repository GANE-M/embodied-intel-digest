"""Orchestration only (v1.4). Storage via build_store(config), never JsonStore inline."""

from __future__ import annotations

import os
import uuid

from app import constants
from app.config import (
    AppConfig,
    load_config,
    load_delivery_targets,
    load_json_config,
    load_keyword_rules,
    load_scoring_config,
    load_tracked_entities,
    validate_config,
)
from app.models import DeliveryTarget, ProcessedItem, RawItem, RunMetadata, ScoringConfig
from app.notifiers.email_sender import EmailNotifier
from app.outputs.digest_builder import (
    build_digest_subject,
    build_plaintext_digest,
)
from app.outputs.html_builder import build_html_digest
from app.outputs.review_exporter import export_review_runs
from app.processors.cleaner import clean_raw_item
from app.processors.classifier import classify_item
from app.processors.deduper import dedupe_items, filter_new_items
from app.processors.llm_judge import build_deepseek_bilingual_summary
from app.processors.scorer import score_item
from app.processors.stage1_selector import select_stage1_candidates
from app.processors.stage2_selector import (
    STAGE2_FAILED,
    STAGE2_SUCCESS_EMPTY,
    STAGE2_UNAVAILABLE,
    select_stage2_items,
)
from app.processors.summarizer import summarize_item_zh
from app.sources.arxiv_source import ArxivSource
from app.sources.base import BaseSource
from app.sources.company_site_source import CompanySiteSource
from app.sources.event_source import EventSource
from app.sources.github_source import GitHubSource
from app.sources.openalex_source import OpenAlexSource
from app.sources.rss_source import RSSSource
from app.storage.base import BaseStore
from app.storage.factory import build_store
from app.utils.logger import get_logger
from app.utils.time_utils import compute_since, format_date, now_in_tz, now_utc


def _is_arxiv_rss_duplicate(feed: dict) -> bool:
    """arXiv ingestion is handled by ``ArxivSource``; skip duplicate RSS URLs."""
    u = str(feed.get("url", "")).lower()
    return "arxiv.org" in u and "rss" in u


def build_sources(config: AppConfig) -> list[BaseSource]:
    d = config.configs_dir
    rules = load_keyword_rules(d)
    literal_keywords = [r.pattern for r in rules if r.match_type == "literal" and r.pattern.strip()]

    categories = [
        x.strip()
        for x in os.getenv("ARXIV_CATEGORIES", "cs.RO").split(",")
        if x.strip()
    ]
    sources: list[BaseSource] = [
        ArxivSource(categories, literal_keywords or ["robotics"]),
        OpenAlexSource(literal_keywords or ["embodied intelligence"], []),
    ]

    repos_cfg = load_json_config(d / "tracked_repos.json")
    if isinstance(repos_cfg, list):
        repos_list = [
            r
            for r in repos_cfg
            if isinstance(r, dict) and r.get("enabled", True) and r.get("repo")
        ]
        if repos_list:
            sources.append(GitHubSource(repos_list))

    feeds = load_json_config(d / "tracked_feeds.json")
    if isinstance(feeds, list) and feeds:
        feeds_use = [f for f in feeds if isinstance(f, dict) and not _is_arxiv_rss_duplicate(f)]
        if feeds_use:
            sources.append(RSSSource(feeds_use))

    events = load_json_config(d / "tracked_events.json")
    if isinstance(events, list) and events:
        sources.append(EventSource(events))

    sites_path = d / "tracked_company_sites.json"
    if sites_path.is_file():
        sites = load_json_config(sites_path)
        if isinstance(sites, list) and sites:
            sources.append(CompanySiteSource(sites))

    return sources


def build_email_notifiers(config: AppConfig) -> list[tuple[DeliveryTarget, EmailNotifier]]:
    """One ``EmailNotifier`` per ``DeliveryTarget`` (multi-SMTP / multi-route)."""
    out: list[tuple[DeliveryTarget, EmailNotifier]] = []
    for t in load_delivery_targets(config.configs_dir):
        out.append(
            (
                t,
                EmailNotifier(
                    t.smtp_host,
                    t.smtp_port,
                    t.smtp_username,
                    t.smtp_password,
                    t.email_from,
                    t.email_to,
                    use_ssl=t.use_ssl,
                ),
            ),
        )
    return out


def collect_all_sources(
    since,
    sources: list[BaseSource],
) -> tuple[list[RawItem], list[dict]]:
    log = get_logger(__name__)
    out: list[RawItem] = []
    errors: list[dict] = []
    for src in sources:
        class_name = type(src).__name__
        try:
            fetched = src.fetch(since)
            n = len(fetched)
            log.info("%s fetched %d items", class_name, n)
            out.extend(fetched)
        except Exception as exc:  # noqa: BLE001
            st = getattr(src, "source_type", class_name)
            errors.append({"source_type": st, "error": str(exc)})
            log.info("%s fetched %d items", class_name, 0)
            log.warning("source %s failed: %s", st, exc)
    return out, errors


def process_items(
    raw_items: list[RawItem],
    config: AppConfig,
    scoring_config: ScoringConfig,
) -> list[ProcessedItem]:
    keyword_rules = load_keyword_rules(config.configs_dir)
    entities = load_tracked_entities(config.configs_dir)
    current_time = now_utc()
    processed: list[ProcessedItem] = []
    for raw in raw_items:
        cleaned = clean_raw_item(raw)
        scored = score_item(
            cleaned,
            keyword_rules,
            entities,
            scoring_config,
            current_time,
        )
        scored.category = classify_item(cleaned)
        processed.append(scored)
    processed = dedupe_items(processed)
    for item in processed:
        item.summary_zh = summarize_item_zh(item, config.summary_mode)
    return processed


def build_digest_payload(
    items: list[ProcessedItem],
    date_str: str,
    top_n: int,
) -> tuple[str, str, str]:
    subject = build_digest_subject(date_str)
    body_text = build_plaintext_digest(items, date_str, top_n)
    body_html = build_html_digest(items, date_str, top_n)
    return subject, body_text, body_html


def run() -> None:
    log = get_logger(__name__)
    config = load_config()
    validate_config(config)
    scoring_config = load_scoring_config()

    store: BaseStore = build_store(config)
    since = compute_since(config.lookback_hours)
    sources = build_sources(config)
    delivery_pairs = build_email_notifiers(config)

    run_id = str(uuid.uuid4())
    started_at = now_utc()

    raw_items, source_errors = collect_all_sources(since, sources)
    log.info("collected %d raw items (%d source errors)", len(raw_items), len(source_errors))

    processed = process_items(raw_items, config, scoring_config)
    log.info("processed %d items after in-run dedupe", len(processed))

    new_items = filter_new_items(processed, store)
    new_items.sort(key=lambda x: x.final_score, reverse=True)

    candidates = select_stage1_candidates(new_items, config)

    to_send, stage2_status, stage2_shortlist = select_stage2_items(candidates, config, log)

    if to_send:
        api_key = (config.llm_api_key or "").strip()
        base_url = (config.llm_base_url or "").strip()
        if api_key and base_url:
            for item in to_send:
                summary_en, summary_zh = build_deepseek_bilingual_summary(
                    item,
                    api_key=api_key,
                    base_url=base_url,
                )
                if summary_en:
                    item.summary_en = summary_en
                if summary_zh:
                    item.summary_zh = summary_zh

    export_review_runs(
        config.state_dir,
        run_id,
        new_items,
        stage2_shortlist,
        to_send,
        log,
    )

    date_str = format_date(now_in_tz(config.timezone), config.timezone)
    status = constants.RUN_STATUS_SUCCESS
    stage2_degraded = stage2_status in (STAGE2_UNAVAILABLE, STAGE2_FAILED)
    if stage2_degraded:
        status = constants.RUN_STATUS_PARTIAL
    delivery_failures = 0

    try:
        if to_send:
            subject, body_text, body_html = build_digest_payload(
                to_send,
                date_str,
                config.top_n,
            )
            if stage2_degraded:
                subject = f"[DEGRADED_STAGE1_ONLY] {subject}"
                log.warning(
                    "stage2 degraded (%s): sending digest with stage1 fallback",
                    stage2_status,
                )
            any_ok = False
            for target, notifier in delivery_pairs:
                try:
                    notifier.send(subject, body_text, body_html)
                    any_ok = True
                    log.info(
                        "digest sent OK via delivery target %r (%d recipients)",
                        target.name,
                        len(target.email_to),
                    )
                except Exception as exc:  # noqa: BLE001
                    delivery_failures += 1
                    log.error("digest send failed for delivery target %r: %s", target.name, exc)
            if any_ok:
                store.mark_seen(to_send)
                log.info("marked %d items seen (>=1 delivery target succeeded)", len(to_send))
            else:
                log.error("all delivery targets failed; not marking items seen")
                status = constants.RUN_STATUS_FAILED
            if delivery_failures and any_ok:
                status = constants.RUN_STATUS_PARTIAL
        else:
            log.info("no unseen items to send")
        if source_errors and status == constants.RUN_STATUS_SUCCESS:
            status = constants.RUN_STATUS_PARTIAL
    except Exception:
        log.exception("digest pipeline failed")
        status = constants.RUN_STATUS_FAILED

    finished_at = now_utc()
    err_total = len(source_errors) + delivery_failures
    store.save_run_metadata(
        RunMetadata(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            item_count=len(to_send),
            error_count=err_total,
        ),
    )


def main() -> None:
    run()


if __name__ == "__main__":
    main()
