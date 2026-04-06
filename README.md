# embodied-intel-digest

Daily digest for embodied-AI signals: collect from several APIs and feeds, score and dedupe, email a ranked digest. Specs align with **`embodied_intel_digest_interface_spec_v1_3_db_ready`**, Cursor **`cursor_instruction_document_embodied_intel_digest_v1_4`**, and config samples from **`cursor_supplemental_generation_checklist_16_files_v1_1`**.

## What it does today

- **Sources (implemented):** RSS/Atom (`RSSSource`), GitHub releases + recent commits (`GitHubSource`), arXiv Atom (`ArxivSource`), OpenAlex (`OpenAlexSource`), static event rows from config (`EventSource`), optional company-site hook (`CompanySiteSource` — scrape returns empty until you extend it).
- **Pipeline:** `source → clean / classify / score / dedupe → plaintext + HTML digest → SMTP notifier`.
- **State:** `BaseStore` with `JsonStore` (file under `STATE_DIR`) or `MemoryStore` (tests). Cross-run dedupe uses `dedupe_id`. **GitHub Actions:** the default Ubuntu runner disk is **ephemeral** — `STATE_DIR` under `${{ github.workspace }}` is **not** preserved across scheduled runs, so the same items may be re-sent unless you point `STATE_DIR` at durable storage (S3/NFS/artifact you restore) or switch to a future DB-backed store. The workflow and this README call that out so you can plan persistence explicitly.

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

- **SMTP / email (legacy single target):** `EMAIL_TO` (comma-separated allowed), `EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, optional `SMTP_USE_SSL=true` for SMTP_SSL (e.g. QQ on 465)
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
| `delivery_targets.json` | Optional; multi-SMTP delivery (see below). If missing or `[]`, env SMTP vars define one target. |

### Multiple recipients and multiple SMTP servers

Copy `configs/delivery_targets.example.json` to `configs/delivery_targets.json` and edit. Each object is one **delivery target**: its own `smtp_host`, `smtp_port`, `email_from`, `email_to` list, and `use_ssl`.

- **Gmail / typical 587:** `use_ssl: false` → client uses `SMTP` + `STARTTLS`.
- **QQ / common 465:** `use_ssl: true` → client uses `SMTP_SSL` (not STARTTLS on a plain socket).

**Passwords:** put **no secrets in JSON**. Use `smtp_password_env` with the name of an environment variable (e.g. `SMTP_PASSWORD_GMAIL`); set the real password in `.env` locally or in GitHub **Secrets** for Actions.

**Local quick test:** configure two targets with different `smtp_password_env` vars, export both passwords, run `python -m app.main`, and confirm logs show each target name.

**GitHub Actions:** add secrets for each env var referenced in `delivery_targets.json` (e.g. `SMTP_PASSWORD_GMAIL`, `SMTP_PASSWORD_QQ`). You can keep using a single legacy SMTP block in the workflow instead until you commit a `delivery_targets.json` that references those secret names.

**Send + dedupe policy:** the same digest body is sent through **each** enabled target. **`mark_seen` runs if at least one target succeeds**, so recipients who got mail are not re-queued; failed targets are logged and the run may be marked `partial_success`.

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

## Repository hygiene (`.gitignore`)

Generated paths such as `__pycache__/`, `state/`, `.state/`, `.env`, and virtualenvs are listed in `.gitignore`. If `state/` or `__pycache__/` was committed earlier, stop tracking without deleting your working copy:

```bash
git rm -r --cached state/ __pycache__/ 2>/dev/null || true
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
