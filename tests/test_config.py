"""config: delivery targets + recipients normalization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import (
    AppConfig,
    load_delivery_targets,
    normalize_recipients,
    validate_config,
)


def test_normalize_recipients_string() -> None:
    assert normalize_recipients("a@x.com, b@y.com") == ["a@x.com", "b@y.com"]


def test_normalize_recipients_list() -> None:
    assert normalize_recipients([" x@z.org ", ""]) == ["x@z.org"]


def test_load_delivery_targets_from_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_PASSWORD_GMAIL", raising=False)
    cfg_path = tmp_path / "delivery_targets.json"
    cfg_path.write_text(
        json.dumps(
            [
                {
                    "name": "t1",
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 587,
                    "smtp_username": "u@example.com",
                    "smtp_password_env": "SMTP_PASSWORD_GMAIL",
                    "email_from": "u@example.com",
                    "email_to": ["r@example.com"],
                    "use_ssl": False,
                    "enabled": True,
                },
            ],
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SMTP_PASSWORD_GMAIL", "secret123")
    targets = load_delivery_targets(tmp_path)
    assert len(targets) == 1
    assert targets[0].name == "t1"
    assert targets[0].smtp_password == "secret123"
    assert targets[0].email_to == ["r@example.com"]
    assert targets[0].use_ssl is False


def test_load_delivery_targets_missing_password_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_PASSWORD_GMAIL", raising=False)
    cfg_path = tmp_path / "delivery_targets.json"
    cfg_path.write_text(
        json.dumps(
            [
                {
                    "name": "t1",
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 587,
                    "smtp_username": "u@example.com",
                    "smtp_password_env": "SMTP_PASSWORD_GMAIL",
                    "email_from": "u@example.com",
                    "email_to": ["r@example.com"],
                    "enabled": True,
                },
            ],
        ),
        encoding="utf-8",
    )
    targets = load_delivery_targets(tmp_path)
    assert targets[0].smtp_password == ""


def test_load_delivery_targets_fallback_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "h")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("EMAIL_FROM", "from@x.com")
    monkeypatch.setenv("EMAIL_TO", "a@b.com, c@d.com")
    targets = load_delivery_targets(tmp_path)
    assert len(targets) == 1
    assert targets[0].name == "default_env"
    assert targets[0].email_to == ["a@b.com", "c@d.com"]


def test_load_delivery_targets_empty_file_uses_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "delivery_targets.json").write_text("[]", encoding="utf-8")
    monkeypatch.setenv("SMTP_HOST", "h")
    monkeypatch.setenv("SMTP_USERNAME", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("EMAIL_FROM", "f@x.com")
    monkeypatch.setenv("EMAIL_TO", "t@x.com")
    targets = load_delivery_targets(tmp_path)
    assert targets[0].name == "default_env"


def test_validate_config_rejects_missing_password(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_PASSWORD_GMAIL", raising=False)
    cfg_path = tmp_path / "delivery_targets.json"
    cfg_path.write_text(
        json.dumps(
            [
                {
                    "name": "t1",
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 587,
                    "smtp_username": "u@example.com",
                    "smtp_password_env": "SMTP_PASSWORD_GMAIL",
                    "email_from": "u@example.com",
                    "email_to": ["r@example.com"],
                    "enabled": True,
                },
            ],
        ),
        encoding="utf-8",
    )
    (tmp_path / "st").mkdir()
    cfg = AppConfig(
        email_to="",
        email_from="",
        email_subject_prefix="S",
        smtp_host="",
        smtp_port=0,
        smtp_username="",
        smtp_password="",
        timezone="UTC",
        top_n=5,
        lookback_hours=24,
        summary_mode="template",
        llm_api_key=None,
        llm_base_url=None,
        store_type="json",
        state_dir=tmp_path / "st",
        database_url=None,
        configs_dir=tmp_path,
        min_final_score=0.35,
        require_keyword_or_entity_hit=False,
    )
    with pytest.raises(ValueError, match="smtp_password"):
        validate_config(cfg)


def test_validate_config_accepts_multi_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_PASSWORD_GMAIL", "x")
    cfg_path = tmp_path / "delivery_targets.json"
    cfg_path.write_text(
        json.dumps(
            [
                {
                    "name": "t1",
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 587,
                    "smtp_username": "u@example.com",
                    "smtp_password_env": "SMTP_PASSWORD_GMAIL",
                    "email_from": "u@example.com",
                    "email_to": ["r@example.com"],
                    "enabled": True,
                },
            ],
        ),
        encoding="utf-8",
    )
    cfg = AppConfig(
        email_to="",
        email_from="",
        email_subject_prefix="S",
        smtp_host="",
        smtp_port=0,
        smtp_username="",
        smtp_password="",
        timezone="UTC",
        top_n=5,
        lookback_hours=24,
        summary_mode="template",
        llm_api_key=None,
        llm_base_url=None,
        store_type="json",
        state_dir=tmp_path / "st",
        database_url=None,
        configs_dir=tmp_path,
        min_final_score=0.35,
        require_keyword_or_entity_hit=False,
    )
    (tmp_path / "st").mkdir()
    validate_config(cfg)
