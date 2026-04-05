# embodied-intel-digest

Daily digest for embodied-AI signals: collect from several APIs and feeds, score and dedupe, email a ranked digest. Specs align with **`embodied_intel_digest_interface_spec_v1_3_db_ready`**, Cursor **`cursor_instruction_document_embodied_intel_digest_v1_4`**, and config samples from **`cursor_supplemental_generation_checklist_16_files_v1_1`**.

## What it does today

- **Sources (implemented):** RSS/Atom (`RSSSource`), GitHub releases + recent commits (`GitHubSource`), arXiv Atom (`ArxivSource`), OpenAlex (`OpenAlexSource`), static event rows from config (`EventSource`), optional company-site hook (`CompanySiteSource` — scrape returns empty until you extend it).
- **Pipeline:** `source → clean / classify / score / dedupe → plaintext + HTML digest → SMTP notifier`.
- **State:** `BaseStore` with `JsonStore` (file under `STATE_DIR`) or `MemoryStore` (tests). Cross-run dedupe uses `dedupe_id`; GitHub Actions runners lose local JSON state each run unless you add external storage or a future DB backend.

## Repository layout

```text
embodied-intel-digest/
├── app/                 # code (main entry: app.main)
├── configs/             # tracked_*.json (see below)
├── tests/
├── requirements.txt
├── .env.example
└── .github/workflows/daily_digest.yml
```

## Install

```bash
pip install -r requirements.txt
```

## Configuration

### Environment

See `.env.example`. Important variables:

- **SMTP / email:** `EMAIL_TO`, `EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
- **Subject:** `EMAIL_SUBJECT_PREFIX` (or legacy `EMAIL_SUBJECT`)
- **Run:** `TIMEZONE`, `TOP_N`, `LOOKBACK_HOURS`, `CONFIGS_DIR`, `ARXIV_CATEGORIES`
- **Storage:** `STORE_TYPE=json`, `STATE_DIR` (defaults to `<project>/.state` when unset)
- **Summary:** `SUMMARY_MODE=template` or `llm`; for `llm` also `LLM_API_KEY`, `LLM_BASE_URL`, optional `LLM_MODEL`
- **Scoring (optional):** `SCORE_*_WEIGHT` env vars
- **Logging:** `LOG_LEVEL`

### `configs/*.json`

All are **strict JSON**: top-level **arrays** `[...]`, no `//` comments, no trailing commas. Extra keys (e.g. `case_sensitive` on keyword rules, `source_preference` on entities) are preserved in files for documentation; **`load_keyword_rules` / `load_tracked_entities` only map fields that exist on `KeywordRule` / `TrackedEntity`** (`type` in JSON maps to `entity_type` in Python).

| File | Role |
|------|------|
| `tracked_keywords.json` | `KeywordRule`: `pattern`, `match_type`, `weight` (+ optional hints) |
| `tracked_entities.json` | `TrackedEntity`: `name`, `aliases`, `type`, `priority` (+ optional `source_preference`) |
| `tracked_feeds.json` | RSS feeds: `name`, `url`, `category`, `enabled` |
| `tracked_repos.json` | GitHub `owner/repo`: `repo`, `enabled`, `priority`, `category` |
| `tracked_events.json` | Event rows: `name`, `url`, `category`, `enabled` |
| `tracked_company_sites.json` | Optional; if present, wires `CompanySiteSource` (still empty until implemented) |

## Run locally

```bash
python -m app.main
```

## GitHub Actions

Workflow installs **only** `pip install -r requirements.txt`, then `python -m app.main`. Configure SMTP-related secrets. Default schedule targets **08:00 China time** via **00:00 UTC** cron; runner disk is ephemeral unless you attach durable storage.

## Tests

```bash
pytest tests/
```

## Architecture (short)

1. **Sources** implement `BaseSource.fetch(since) → list[RawItem]` (errors swallowed inside fetch where implemented).
2. **Processors** normalize, classify (`CATEGORIES`), score (0–1), dedupe, summarize (`template` / optional `llm`).
3. **Outputs** build plaintext (`digest_builder`) and HTML (`html_builder`) with the same grouping order.
4. **Notifiers** implement `BaseNotifier.send(...)`.
5. **Storage** is only through `build_store(config)` — do not construct `JsonStore` in `main` by hand.

## Future extensions (not in this repo yet)

- DB-backed `BaseStore` (`sqlite` / `postgres` / `supabase` placeholders in `build_store`)
- Richer `CompanySiteSource` scraping (e.g. BeautifulSoup-based parsers)
- OAuth / non-SMTP notifiers, Slack, etc.
