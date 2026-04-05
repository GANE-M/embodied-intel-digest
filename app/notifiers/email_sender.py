"""SMTP email notifier (e.g. Gmail with app password)."""

from __future__ import annotations

import smtplib
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
        recipient: str,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._username = username
        self._password = password
        self._sender = sender
        self._recipient = recipient

    def _build_message(
        self,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._sender
        msg["To"] = self._recipient
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))
        return msg

    def _open_connection(self) -> smtplib.SMTP:
        conn = smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=60)
        conn.ehlo()
        conn.starttls()
        conn.ehlo()
        conn.login(self._username, self._password)
        return conn

    def send(self, subject: str, body_text: str, body_html: str | None = None) -> None:
        msg = self._build_message(subject, body_text, body_html)
        with self._open_connection() as conn:
            conn.sendmail(self._sender, [self._recipient], msg.as_string())
