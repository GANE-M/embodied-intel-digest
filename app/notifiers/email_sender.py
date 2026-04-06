"""SMTP email notifier: multi-recipient, STARTTLS or SMTP_SSL (e.g. QQ 465)."""

from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.notifiers.base import BaseNotifier


class EmailNotifier(BaseNotifier):
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        sender: str,
        recipients: list[str],
        *,
        use_ssl: bool = False,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._username = username
        self._password = password
        self._sender = sender
        self._recipients = [r.strip() for r in recipients if r.strip()]
        self._use_ssl = use_ssl

    def _build_message(
        self,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._sender
        msg["To"] = ", ".join(self._recipients)
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))
        return msg

    def _open_connection(self) -> smtplib.SMTP | smtplib.SMTP_SSL:
        ctx = ssl.create_default_context()
        try:
            if self._use_ssl:
                conn = smtplib.SMTP_SSL(
                    self._smtp_host,
                    self._smtp_port,
                    timeout=60,
                    context=ctx,
                )
                conn.ehlo()
                conn.login(self._username, self._password)
                return conn
            conn = smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=60)
            conn.ehlo()
            conn.starttls(context=ctx)
            conn.ehlo()
            conn.login(self._username, self._password)
            return conn
        except OSError as exc:
            raise RuntimeError(
                f"SMTP connection failed ({self._smtp_host}:{self._smtp_port})",
            ) from exc
        except smtplib.SMTPException as exc:
            raise RuntimeError("SMTP authentication or handshake failed") from exc

    def send(self, subject: str, body_text: str, body_html: str | None = None) -> None:
        if not self._recipients:
            raise ValueError("EmailNotifier has no recipients")
        msg = self._build_message(subject, body_text, body_html)
        with self._open_connection() as conn:
            conn.sendmail(self._sender, self._recipients, msg.as_string())
