"""IMAP reader — polls a mailbox and matches inbound replies to our sends.

Plain ``imaplib`` (stdlib), zero cost. This is the "complete look on replies"
half of the engine.

Matching strategy, most reliable first:
  1. The reply's ``In-Reply-To`` / ``References`` headers echo the Message-ID we
     set on the outbound email → exact match via the DB.
  2. Fallback: the From address matches a known recipient with an open thread.

Each reply is keyed by a stable ``mailbox:UID`` so re-polling never
double-records. The reader only fetches; recording + status changes are done by
the caller (see :meth:`fetch_replies`, which returns raw parsed hits).
"""

from __future__ import annotations

import email
import imaplib
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import Message as PyEmailMessage
from email.utils import parseaddr

from modules.common.logger import get_logger
from modules.pulse.inbox import config
from modules.pulse.inbox.schemas import Mailbox

logger = get_logger("pulse.inbox.imap")

_MSGID_RE = re.compile(r"<[^>]+>")


class ImapReader:
    """Reads a mailbox over IMAP and extracts reply candidates."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def fetch_replies(self, mailbox: Mailbox, credentials: dict,
                      lookback_days: int | None = None,
                      known_ids: set[str] | None = None,
                      known_senders: set[str] | None = None) -> list[dict]:
        """Return parsed inbound messages that look like replies to our mail.

        Each item: ``{uid, from_email, subject, body, in_reply_to,
        references, message_id, received_at}``. Matching to our outbound mail is
        left to the caller (it owns the DB). Raises nothing on an empty box;
        connection/auth errors propagate as ``imaplib.IMAP4.error``.

        Speed: searches only UNSEEN mail since the lookback window, and — when
        ``known_ids`` (our sent Message-IDs) is given — batch-fetches just the
        headers to keep only messages that reference one of our emails, then
        downloads the full body for those alone. On a busy inbox this turns a
        few-hundred full fetches into a couple, so a cycle is near-instant.
        """
        host = credentials.get("imap_host") or mailbox.imap_host
        port = int(credentials.get("imap_port") or mailbox.imap_port or 993)
        password = credentials.get("password", "")
        lookback = lookback_days or config.IMAP_LOOKBACK_DAYS

        if not host:
            logger.warning("No IMAP host for %s; skipping poll.", mailbox.email)
            return []

        results: list[dict] = []
        conn = imaplib.IMAP4_SSL(host, port, timeout=self.timeout)
        try:
            conn.login(mailbox.email, password)
            conn.select(config.IMAP_MAILBOX_FOLDER, readonly=True)
            since = (datetime.now(timezone.utc) - timedelta(days=lookback)).strftime("%d-%b-%Y")
            typ, data = conn.search(None, "UNSEEN", "SINCE", since)
            if typ != "OK" or not data or not data[0]:
                return results
            seqs = data[0].split()
            candidates = (self._prefilter(conn, seqs, known_ids or set(), known_senders or set())
                          if (known_ids or known_senders) else seqs)
            for seq in candidates:
                parsed = self._fetch_one(conn, mailbox, seq)
                if parsed:
                    results.append(parsed)
            logger.info("IMAP %s: %d unread, %d matched (our-thread or known sender), %d parsed.",
                        mailbox.email, len(seqs), len(candidates), len(results))
        finally:
            try:
                conn.close()
            except imaplib.IMAP4.error:
                pass
            conn.logout()
        return results

    def _prefilter(self, conn: imaplib.IMAP4_SSL, seqs: list[bytes],
                   known_ids: set[str], known_senders: set[str]) -> list[bytes]:
        """One batched header FETCH → keep seqs that either reference a Message-ID
        we sent OR come from a known recipient's address (Gmail threading means a
        reply often points at an older message in the thread, not our latest)."""
        if not seqs:
            return []
        typ, data = conn.fetch(b",".join(seqs),
                               "(BODY.PEEK[HEADER.FIELDS (IN-REPLY-TO REFERENCES FROM)])")
        if typ != "OK" or not data:
            return seqs  # on any oddity, fall back to scanning all unread
        keep: list[bytes] = []
        for item in data:
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            seq = item[0].split(b" ", 1)[0]
            hdr = email.message_from_bytes(item[1])
            ids = set(_MSGID_RE.findall(hdr.get("References", "") or ""))
            irt = self._first_msgid(hdr.get("In-Reply-To", ""))
            if irt:
                ids.add(irt)
            frm = parseaddr(hdr.get("From", ""))[1].lower()
            if (ids & known_ids) or (frm and frm in known_senders):
                keep.append(seq)
        return keep

    def _fetch_one(self, conn: imaplib.IMAP4_SSL, mailbox: Mailbox, uid: bytes) -> dict | None:
        typ, msg_data = conn.fetch(uid, "(RFC822)")
        if typ != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
            return None
        msg = email.message_from_bytes(msg_data[0][1])
        from_email = parseaddr(msg.get("From", ""))[1].lower()
        # Skip our own outgoing copies that some providers file in the same box.
        if from_email == mailbox.email.lower():
            return None
        return {
            "uid": f"{mailbox.email}:{uid.decode()}",
            "from_email": from_email,
            "subject": self._decode(msg.get("Subject", "")),
            "body": self._body_text(msg),
            "in_reply_to": self._first_msgid(msg.get("In-Reply-To", "")),
            "references": _MSGID_RE.findall(msg.get("References", "") or ""),
            "message_id": self._first_msgid(msg.get("Message-ID", "")),
            "received_at": self._received_at(msg),
        }

    # -- parsing helpers ----------------------------------------------------
    @staticmethod
    def _decode(value: str) -> str:
        try:
            return str(make_header(decode_header(value)))
        except (ValueError, LookupError):
            return value or ""

    @staticmethod
    def _first_msgid(value: str) -> str:
        m = _MSGID_RE.search(value or "")
        return m.group(0) if m else ""

    @staticmethod
    def _received_at(msg: PyEmailMessage) -> str:
        from email.utils import parsedate_to_datetime
        try:
            dt = parsedate_to_datetime(msg.get("Date", ""))
            if dt is not None:
                return dt.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _body_text(msg: PyEmailMessage, max_chars: int = 4000) -> str:
        """Extract a plain-text body, preferring text/plain, HTML-stripped else."""
        text = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition") or "")
                if ctype == "text/plain" and "attachment" not in disp:
                    text = ImapReader._payload(part)
                    break
            if not text:
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        text = ImapReader._strip_html(ImapReader._payload(part))
                        break
        else:
            payload = ImapReader._payload(msg)
            text = payload if msg.get_content_type() == "text/plain" else ImapReader._strip_html(payload)
        return text.strip()[:max_chars]

    @staticmethod
    def _payload(part: PyEmailMessage) -> str:
        try:
            raw = part.get_payload(decode=True)
            if raw is None:
                return ""
            charset = part.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
        except (LookupError, ValueError):
            return ""

    @staticmethod
    def _strip_html(html: str) -> str:
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
