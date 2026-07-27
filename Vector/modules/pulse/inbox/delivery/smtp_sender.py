"""SMTP sender — sends one email via a mailbox, with correct threading headers.

Plain ``smtplib`` (stdlib), zero cost. The important craft here is RFC 5322
threading: every outbound gets a stable ``Message-ID``; follow-ups carry
``In-Reply-To`` + ``References`` pointing at the first message in the thread, so
(a) follow-ups land in the same conversation in the recipient's client, and
(b) when they reply, their client echoes our Message-ID back in *its*
In-Reply-To — which is exactly how :mod:`imap_reader` matches replies to us.

Security transport is chosen by port: 465 → implicit SSL, otherwise STARTTLS.
"""

from __future__ import annotations

import smtplib
import ssl
import uuid
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from modules.common.logger import get_logger
from modules.pulse.inbox.schemas import Mailbox, Message

logger = get_logger("pulse.inbox.smtp")


class SmtpSendError(RuntimeError):
    """Raised when a send fails (auth, connection, or recipient refused)."""


class SmtpSender:
    """Sends :class:`Message` objects through a mailbox's SMTP server."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    @staticmethod
    def new_message_id(from_email: str) -> str:
        """Generate a globally-unique RFC Message-ID anchored to the sender domain."""
        domain = from_email.split("@")[-1] if "@" in from_email else "mail.local"
        return make_msgid(idstring=uuid.uuid4().hex[:12], domain=domain)

    def build_mime(self, mailbox: Mailbox, message: Message) -> EmailMessage:
        """Assemble the MIME message (plain text) with threading headers set."""
        mime = EmailMessage()
        mime["From"] = formataddr((mailbox.from_name or mailbox.email, mailbox.email))
        mime["To"] = message.to_email
        mime["Subject"] = message.subject
        mime["Date"] = formatdate(localtime=True)
        mime["Message-ID"] = message.rfc_message_id or self.new_message_id(mailbox.email)
        mime["Reply-To"] = mailbox.email

        # Threading: a follow-up references the thread root so clients group it.
        if message.in_reply_to:
            mime["In-Reply-To"] = message.in_reply_to
            refs = message.thread_id or message.in_reply_to
            mime["References"] = refs

        mime.set_content(message.body)
        return mime

    def send(self, mailbox: Mailbox, credentials: dict, message: Message) -> Message:
        """Send ``message`` from ``mailbox``. Mutates + returns it with the
        Message-ID it was sent with. Raises :class:`SmtpSendError` on failure.

        ``credentials`` is the live env config dict for this mailbox (holds the
        password + host/port), from :func:`accounts.get_credentials`.
        """
        if not message.rfc_message_id:
            message.rfc_message_id = self.new_message_id(mailbox.email)
        if not message.thread_id:
            # First message in a thread anchors the thread on its own id.
            message.thread_id = message.in_reply_to or message.rfc_message_id
        message.from_email = mailbox.email

        mime = self.build_mime(mailbox, message)
        host = credentials.get("smtp_host") or mailbox.smtp_host
        port = int(credentials.get("smtp_port") or mailbox.smtp_port or 465)
        password = credentials.get("password", "")

        if not host:
            raise SmtpSendError(f"No SMTP host for {mailbox.email}")

        try:
            if port == 465:
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(host, port, timeout=self.timeout, context=ctx) as srv:
                    srv.login(mailbox.email, password)
                    srv.send_message(mime)
            else:
                with smtplib.SMTP(host, port, timeout=self.timeout) as srv:
                    srv.ehlo()
                    srv.starttls(context=ssl.create_default_context())
                    srv.ehlo()
                    srv.login(mailbox.email, password)
                    srv.send_message(mime)
        except (smtplib.SMTPException, ssl.SSLError, OSError) as exc:
            raise SmtpSendError(f"SMTP send to {message.to_email} via {mailbox.email} failed: {exc}") from exc

        logger.info("Sent to %s via %s (msg-id %s)", message.to_email, mailbox.email,
                    message.rfc_message_id)
        return message


class DryRunSender(SmtpSender):
    """A sender that assigns real threading ids but never touches the network.

    Used by the scheduler's ``dry_run`` mode and tests: message state advances
    exactly as a live send would (Message-ID, thread linkage), only nothing
    leaves the machine.
    """

    def send(self, mailbox: Mailbox, credentials: dict, message: Message) -> Message:
        if not message.rfc_message_id:
            message.rfc_message_id = self.new_message_id(mailbox.email)
        if not message.thread_id:
            message.thread_id = message.in_reply_to or message.rfc_message_id
        message.from_email = mailbox.email
        logger.info("[dry-run] would send to %s via %s (msg-id %s)",
                    message.to_email, mailbox.email, message.rfc_message_id)
        return message
