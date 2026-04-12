"""Environment + JSON loading only (v1.4)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app import constants
from app.models import DeliveryTarget, FilterRules, KeywordRule, ScoringConfig, TrackedEntity


@dataclass
class AppConfig:
    email_to: str
    email_from: str
    email_subject_prefix: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    timezone: str
    top_n: int
    lookback_hours: int
    summary_mode: str
    llm_api_key: str | None
    llm_base_url: str | None
    store_type: str
    state_dir: Path | None
    database_url: str | None
    configs_dir: Path
    min_final_score: float
    require_keyword_or_entity_hit: bool
    filter_rules: FilterRules
    stage2_shortlist_multiplier: int


def _parse_state_dir(raw: str | None) -> Path | None:
    if raw is None or not str(raw).strip():
        return None
    return Path(raw).resolve()


def load_config() -> AppConfig:
    load_dotenv()
    configs_dir = Path(os.getenv("CONFIGS_DIR", "configs")).resolve()
    store_type = (os.getenv("STORE_TYPE", constants.STORE_TYPES_JSON) or "json").lower().strip()
    state_dir = _parse_state_dir(os.getenv("STATE_DIR"))
    if store_type == constants.STORE_TYPES_JSON and state_dir is None:
        state_dir = (configs_dir.parent / ".state").resolve()

    top_n = int(os.getenv("TOP_N", str(constants.DEFAULT_TOP_N)))
    lookback_hours = int(
        os.getenv("LOOKBACK_HOURS", str(constants.DEFAULT_LOOKBACK_HOURS)),
    )
    summary_mode = (
        os.getenv("SUMMARY_MODE", constants.DEFAULT_SUMMARY_MODE) or "template"
    ).lower().strip()

    llm_key = os.getenv("LLM_API_KEY") or None
    llm_url = os.getenv("LLM_BASE_URL") or None
    if not str(llm_key or "").strip():
        llm_key = None
    if not str(llm_url or "").strip():
        llm_url = None

    min_final = float(os.getenv("MIN_FINAL_SCORE", str(constants.DEFAULT_MIN_FINAL_SCORE)))
    require_hit = (os.getenv("REQUIRE_KEYWORD_OR_ENTITY_HIT", "true") or "").lower() in (
        "1",
        "true",
        "yes",
    )

    stage2_mult_raw = os.getenv(
        "STAGE2_SHORTLIST_MULTIPLIER",
        str(constants.DEFAULT_STAGE2_SHORTLIST_MULTIPLIER),
    )
    try:
        stage2_mult = int(str(stage2_mult_raw).strip() or "2")
    except ValueError:
        stage2_mult = constants.DEFAULT_STAGE2_SHORTLIST_MULTIPLIER
    stage2_mult = max(1, min(5, stage2_mult))

    filter_rules = load_filter_rules(configs_dir)

    cfg = AppConfig(
        email_to=os.getenv("EMAIL_TO", ""),
        email_from=os.getenv("EMAIL_FROM", ""),
        email_subject_prefix=(
            os.getenv("EMAIL_SUBJECT_PREFIX")
            or os.getenv("EMAIL_SUBJECT")
            or "Embodied Intel Digest"
        ),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        timezone=os.getenv("TIMEZONE") or "UTC",
        top_n=top_n,
        lookback_hours=lookback_hours,
        summary_mode=summary_mode,
        llm_api_key=llm_key,
        llm_base_url=llm_url,
        store_type=store_type,
        state_dir=state_dir,
        database_url=os.getenv("DATABASE_URL") or None,
        configs_dir=configs_dir,
        min_final_score=min(1.0, max(0.0, min_final)),
        require_keyword_or_entity_hit=require_hit,
        filter_rules=filter_rules,
        stage2_shortlist_multiplier=stage2_mult,
    )
    return cfg


def normalize_recipients(value: Any) -> list[str]:
    """Coerce env string or JSON value into a non-empty stripped address list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    s = str(value).strip()
    if not s:
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


def _delivery_target_from_env() -> DeliveryTarget:
    use_ssl = (os.getenv("SMTP_USE_SSL", "") or "").lower() in ("1", "true", "yes")
    return DeliveryTarget(
        name="default_env",
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        email_from=os.getenv("EMAIL_FROM", ""),
        email_to=normalize_recipients(os.getenv("EMAIL_TO", "")),
        use_ssl=use_ssl,
        enabled=True,
    )


def _parse_delivery_target_row(row: dict[str, Any]) -> DeliveryTarget | None:
    if not row.get("enabled", True):
        return None
    name = str(row.get("name", "") or "target").strip() or "target"
    host = str(row.get("smtp_host", "") or "").strip()
    port_raw = row.get("smtp_port", 587)
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        port = 587
    user = str(row.get("smtp_username", "") or "").strip()
    env_key = row.get("smtp_password_env")
    pwd = ""
    if env_key is not None and str(env_key).strip():
        pwd = os.getenv(str(env_key).strip(), "") or ""
    frm = str(row.get("email_from", "") or "").strip()
    recipients = normalize_recipients(row.get("email_to"))
    use_ssl = bool(row.get("use_ssl", False))
    return DeliveryTarget(
        name=name,
        smtp_host=host,
        smtp_port=port,
        smtp_username=user,
        smtp_password=pwd,
        email_from=frm,
        email_to=recipients,
        use_ssl=use_ssl,
        enabled=True,
    )


def load_delivery_targets(configs_dir: Path) -> list[DeliveryTarget]:
    """Load ``configs/delivery_targets.json`` if present and non-empty; else env fallback."""
    path = configs_dir / "delivery_targets.json"
    if path.is_file():
        try:
            data = load_json_config(path)
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, list) and len(data) > 0:
            out: list[DeliveryTarget] = []
            for row in data:
                if not isinstance(row, dict):
                    continue
                t = _parse_delivery_target_row(row)
                if t is not None:
                    out.append(t)
            if out:
                return out
    return [_delivery_target_from_env()]


def validate_config(config: AppConfig) -> None:
    targets = load_delivery_targets(config.configs_dir)
    problems: list[str] = []
    for t in targets:
        prefix = f"{t.name!r}: "
        if not t.smtp_host.strip():
            problems.append(prefix + "smtp_host")
        if not t.smtp_username.strip():
            problems.append(prefix + "smtp_username")
        if not t.smtp_password.strip():
            problems.append(prefix + "smtp_password (or smtp_password env)")
        if not t.email_from.strip():
            problems.append(prefix + "email_from")
        if not t.email_to:
            problems.append(prefix + "email_to")
    if problems:
        raise ValueError(
            "Invalid delivery target configuration: " + "; ".join(problems),
        )
    if not config.configs_dir.is_dir():
        raise ValueError(f"configs_dir is not a directory: {config.configs_dir}")
    if config.store_type == constants.STORE_TYPES_JSON and config.state_dir is None:
        raise ValueError("state_dir missing for store_type=json")
    if config.summary_mode not in constants.SUMMARY_MODES:
        raise ValueError(
            f"Invalid SUMMARY_MODE {config.summary_mode!r}; expected one of {constants.SUMMARY_MODES}",
        )
    if config.summary_mode == "llm":
        if not config.llm_api_key or not config.llm_base_url:
            raise ValueError("summary_mode=llm requires LLM_API_KEY and LLM_BASE_URL")


def load_json_config(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_filter_rules(configs_dir: Path) -> FilterRules:
    """Load ``configs/filter_rules.json`` (minimal schema: block/allow lists)."""
    path = configs_dir / "filter_rules.json"
    if not path.is_file():
        return FilterRules()

    try:
        data = load_json_config(path)
    except (OSError, json.JSONDecodeError):
        return FilterRules()

    if not isinstance(data, dict):
        return FilterRules()

    def _str_list(key: str) -> list[str]:
        raw = data.get(key, [])
        if not isinstance(raw, list):
            return []
        return [str(x).strip() for x in raw if str(x).strip()]

    return FilterRules(
        title_blocklist=_str_list("title_blocklist"),
        url_blocklist=_str_list("url_blocklist"),
        source_blocklist=_str_list("source_blocklist"),
        source_allowlist=_str_list("source_allowlist"),
    )


def load_keyword_rules(configs_dir: Path) -> list[KeywordRule]:
    data = load_json_config(configs_dir / "tracked_keywords.json")
    out: list[KeywordRule] = []
    if isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                continue
            pattern = str(row.get("pattern", "")).strip()
            if not pattern:
                continue
            mt = str(row.get("match_type", "literal")).lower().strip()
            if mt not in ("literal", "regex"):
                mt = "literal"
            weight = float(row.get("weight", 1.0))
            cs = bool(row.get("case_sensitive", False))
            ch = str(row.get("category_hint", "") or "").strip()
            out.append(
                KeywordRule(
                    pattern=pattern,
                    match_type=mt,
                    weight=weight,
                    case_sensitive=cs,
                    category_hint=ch,
                ),
            )
        return out
    if isinstance(data, dict):
        for k, v in data.items():
            out.append(KeywordRule(pattern=str(k), match_type="literal", weight=float(v)))
    return out


def load_tracked_entities(configs_dir: Path) -> list[TrackedEntity]:
    data = load_json_config(configs_dir / "tracked_entities.json")
    if not isinstance(data, list):
        return []
    out: list[TrackedEntity] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        aliases = [str(a).strip() for a in (row.get("aliases") or []) if str(a).strip()]
        etype = str(row.get("entity_type") or row.get("type", "") or "").strip()
        priority = float(row.get("priority", 1.0))
        sp_raw = row.get("source_preference")
        if isinstance(sp_raw, list):
            source_pref = [str(x).strip() for x in sp_raw if str(x).strip()]
        elif isinstance(sp_raw, str) and sp_raw.strip():
            source_pref = [p.strip() for p in sp_raw.split(",") if p.strip()]
        else:
            source_pref = []
        out.append(
            TrackedEntity(
                name=name,
                aliases=aliases,
                entity_type=etype,
                priority=priority,
                source_preference=source_pref,
            ),
        )
    return out


def load_scoring_config() -> ScoringConfig:
    def _f(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None or not str(raw).strip():
            return default
        return float(raw)

    sw = {k: min(1.0, max(0.0, float(v))) for k, v in constants.DEFAULT_SOURCE_WEIGHTS.items()}
    return ScoringConfig(
        source_weights=sw,
        keyword_weight=_f("SCORE_KEYWORD_WEIGHT", constants.DEFAULT_KEYWORD_WEIGHT),
        entity_weight=_f("SCORE_ENTITY_WEIGHT", constants.DEFAULT_ENTITY_WEIGHT),
        freshness_weight=_f("SCORE_FRESHNESS_WEIGHT", constants.DEFAULT_FRESHNESS_WEIGHT),
        source_weight=_f("SCORE_SOURCE_WEIGHT", constants.DEFAULT_SOURCE_SCORE_WEIGHT),
    )
