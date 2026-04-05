"""Orchestration only (v1.4). Storage via build_store(config), never JsonStore inline."""

from __future__ import annotations

import os
import uuid

from app import constants
from app.config import (
    AppConfig,
    load_config,
    load_json_config,
    load_keyword_rules,
    load_scoring_config,
    load_tracked_entities,
    validate_config,
)
from app.models import ProcessedItem, RawItem, RunMetadata, ScoringConfig
from app.notifiers.base import BaseNotifier
from app.notifiers.email_sender import EmailNotifier
from app.outputs.digest_builder import (
    build_digest_subject,
    build_plaintext_digest,
)
from app.outputs.html_builder import build_html_digest
from app.processors.cleaner import clean_raw_item
from app.processors.classifier import classify_item
from app.processors.deduper import dedupe_items, filter_new_items
from app.processors.scorer import score_item
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
    # arXiv papers: use ArxivSource only (not RSS feeds pointing at arxiv.org/rss/...).
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


def build_notifier(config: AppConfig) -> BaseNotifier:
    return EmailNotifier(
        config.smtp_host,
        config.smtp_port,
        config.smtp_username,
        config.smtp_password,
        config.email_from,
        config.email_to,
    )


def collect_all_sources(
    since,
    sources: list[BaseSource],
) -> tuple[list[RawItem], list[dict]]:
    log = get_logger(__name__)
    out: list[RawItem] = []
    errors: list[dict] = []
    for src in sources:
        try:
            out.extend(src.fetch(since))
        except Exception as exc:  # noqa: BLE001
            st = getattr(src, "source_type", type(src).__name__)
            errors.append({"source_type": st, "error": str(exc)})
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


def build_and_send_digest(
    items: list[ProcessedItem],
    notifier: BaseNotifier,
    date_str: str,
    top_n: int,
) -> None:
    subject = build_digest_subject(date_str)
    body_text = build_plaintext_digest(items, date_str, top_n)
    body_html = build_html_digest(items, date_str, top_n)
    notifier.send(subject, body_text, body_html)


def run() -> None:
    log = get_logger(__name__)
    config = load_config()
    validate_config(config)
    scoring_config = load_scoring_config()

    store: BaseStore = build_store(config)
    since = compute_since(config.lookback_hours)
    sources = build_sources(config)
    notifier = build_notifier(config)

    run_id = str(uuid.uuid4())
    started_at = now_utc()

    raw_items, source_errors = collect_all_sources(since, sources)
    log.info("collected %d raw items (%d source errors)", len(raw_items), len(source_errors))

    processed = process_items(raw_items, config, scoring_config)
    log.info("processed %d items after in-run dedupe", len(processed))

    new_items = filter_new_items(processed, store)
    new_items.sort(key=lambda x: x.final_score, reverse=True)
    candidates = [x for x in new_items if x.final_score >= config.min_final_score]
    if config.require_keyword_or_entity_hit:
        candidates = [x for x in candidates if x.matched_keywords or x.matched_entities]
    to_send = candidates[: config.top_n]

    date_str = format_date(now_in_tz(config.timezone), config.timezone)
    status = constants.RUN_STATUS_SUCCESS

    try:
        if to_send:
            build_and_send_digest(to_send, notifier, date_str, config.top_n)
            store.mark_seen(to_send)
            log.info("sent digest with %d new items", len(to_send))
        else:
            log.info("no unseen items to send")
        if source_errors:
            status = constants.RUN_STATUS_PARTIAL
    except Exception:
        log.exception("digest send failed")
        status = constants.RUN_STATUS_FAILED

    finished_at = now_utc()
    store.save_run_metadata(
        RunMetadata(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            item_count=len(to_send),
            error_count=len(source_errors),
        ),
    )


def main() -> None:
    run()


if __name__ == "__main__":
    main()
