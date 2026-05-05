import os
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from models.partner import Company, OutreachEmail, EmailStatus


@dataclass
class SMTPConfig:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True

    @classmethod
    def from_env(cls) -> "SMTPConfig":
        """Load SMTP settings from environment variables."""
        return cls(
            host=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
            port=int(os.environ.get("SMTP_PORT", "587")),
            username=os.environ.get("SMTP_USERNAME", ""),
            password=os.environ.get("SMTP_PASSWORD", ""),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.username and self.password)


class EmailSendError(Exception):
    pass


class EmailSender:
    """
    Handles the full SMTP sending protocol for outreach emails.

    Supports:
    - Real sending via SMTP (Gmail, Outlook, etc.)
    - Dry-run mode (prints what would be sent, no network calls)

    Usage:
        config = SMTPConfig.from_env()
        sender = EmailSender(company, config, dry_run=True)
        sender.send(outreach_email)
    """

    def __init__(self, company: Company, config: SMTPConfig, dry_run: bool = True):
        self.company = company
        self.config = config
        self.dry_run = dry_run

        if not dry_run and not config.is_configured:
            raise EmailSendError(
                "SMTP_USERNAME and SMTP_PASSWORD must be set to send real emails.\n"
                "Run with dry_run=True to preview without sending."
            )

    def _build_mime(self, email: OutreachEmail) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = email.subject
        msg["From"] = f"{self.company.sender_name} <{self.company.sender_email}>"
        msg["To"] = email.partner.email
        msg["Reply-To"] = self.company.sender_email

        # Plain-text part
        msg.attach(MIMEText(email.body, "plain", "utf-8"))

        # Basic HTML part (wraps plain text)
        html_body = email.body.replace("\n", "<br>")
        html = f"""<html><body>
<p style="font-family:sans-serif;font-size:15px;line-height:1.7;color:#222;">
{html_body}
</p></body></html>"""
        msg.attach(MIMEText(html, "html", "utf-8"))

        return msg

    def _send_smtp(self, msg: MIMEMultipart, recipient: str):
        context = ssl.create_default_context()
        with smtplib.SMTP(self.config.host, self.config.port) as server:
            server.ehlo()
            if self.config.use_tls:
                server.starttls(context=context)
                server.ehlo()
            server.login(self.config.username, self.config.password)
            server.sendmail(self.config.sender_email, recipient, msg.as_string())

    def send(self, email: OutreachEmail) -> bool:
        """
        Send (or dry-run) a single OutreachEmail.
        Returns True on success, False on failure.
        Updates email.sent_at and partner.status in-place.
        """
        if self.dry_run:
            print(f"  [dry-run] Would send to {email.partner.email}: \"{email.subject}\"")
            email.sent_at = datetime.now()
            email.partner.status = EmailStatus.SENT
            return True

        try:
            msg = self._build_mime(email)
            self._send_smtp(msg, email.partner.email)
            email.sent_at = datetime.now()
            email.partner.status = EmailStatus.SENT
            return True
        except (smtplib.SMTPException, OSError) as e:
            email.error = str(e)
            email.partner.status = EmailStatus.FAILED
            raise EmailSendError(f"Failed to send to {email.partner.email}: {e}") from e

    def send_batch(self, emails: list[OutreachEmail]) -> tuple[int, int]:
        """
        Send all emails. Returns (success_count, failure_count).
        """
        success, failure = 0, 0
        for email in emails:
            try:
                self.send(email)
                success += 1
            except EmailSendError as e:
                print(f"  [error] {e}")
                failure += 1
        return success, failure
