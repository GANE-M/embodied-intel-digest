"""EmailNotifier: message shape + SMTP vs SMTP_SSL (mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.notifiers.email_sender import EmailNotifier


def test_build_message_multi_recipient_to_header() -> None:
    n = EmailNotifier(
        "h",
        587,
        "u",
        "p",
        "from@x.com",
        ["a@b.com", "c@d.com"],
        use_ssl=False,
    )
    msg = n._build_message("Subj", "plain body", "<p>h</p>")
    assert msg["To"] == "a@b.com, c@d.com"
    assert msg["From"] == "from@x.com"


def test_send_uses_smtp_starttls_path() -> None:
    n = EmailNotifier(
        "smtp.gmail.com",
        587,
        "u",
        "p",
        "from@x.com",
        ["to@x.com"],
        use_ssl=False,
    )
    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp
    mock_smtp.__exit__.return_value = None
    mock_ctx = MagicMock()
    with (
        patch("app.notifiers.email_sender.smtplib.SMTP", return_value=mock_smtp),
        patch("app.notifiers.email_sender.ssl.create_default_context", return_value=mock_ctx),
    ):
        n.send("s", "t", None)
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once()
    mock_smtp.sendmail.assert_called_once()
    args = mock_smtp.sendmail.call_args[0]
    assert args[1] == ["to@x.com"]


def test_send_uses_smtp_ssl_path() -> None:
    n = EmailNotifier(
        "smtp.qq.com",
        465,
        "u",
        "p",
        "from@qq.com",
        ["to@qq.com"],
        use_ssl=True,
    )
    mock_ssl = MagicMock()
    mock_ssl.__enter__.return_value = mock_ssl
    mock_ssl.__exit__.return_value = None
    with (
        patch("app.notifiers.email_sender.smtplib.SMTP_SSL", return_value=mock_ssl),
        patch("app.notifiers.email_sender.ssl.create_default_context", return_value=MagicMock()),
    ):
        n.send("s", "t", None)
    mock_ssl.login.assert_called_once()
    mock_ssl.sendmail.assert_called_once()


def test_send_empty_recipients_raises() -> None:
    n = EmailNotifier("h", 25, "u", "p", "f", [], use_ssl=False)
    with pytest.raises(ValueError, match="no recipients"):
        n.send("s", "t", None)
