"""UnipileProvider — real LinkedIn transport via Unipile's unified API.

Unipile hosts the LinkedIn session + proxy for you (you connect the account once
via their Hosted Auth wizard), so we never touch raw cookies. Its endpoints map
almost 1:1 onto our interface:

    POST /api/v1/users/invite                 send a connection invitation
    GET  /api/v1/users/{identifier}?account_id=…   resolve provider_id + network distance
    POST /api/v1/chats                        start a chat / send a message
    GET  /api/v1/chats?account_id=…           list chats
    GET  /api/v1/chats/{id}/messages          list messages in a chat

Auth: ``X-API-KEY``. Base URL: ``https://{UNIPILE_DSN}/api/v1`` (DSN is the
host:port from your dashboard). Acceptance is detected by re-reading a profile's
``network_distance`` (DISTANCE_1 == 1st-degree connection).
"""

from __future__ import annotations

import re

import httpx

from modules.common.logger import get_logger
from modules.pulse.connect import config
from modules.pulse.connect.schemas import ActionResult, InboundMessage, LinkedInAccount, utcnow_iso

logger = get_logger("pulse.connect.unipile")

_SLUG_RE = re.compile(r"linkedin\.com/in/([^/?#]+)", re.IGNORECASE)


class UnipileError(RuntimeError):
    pass


class UnipileProvider:
    name = "unipile"

    def __init__(self) -> None:
        self.api_key = config.UNIPILE_API_KEY
        dsn = config.UNIPILE_DSN.replace("https://", "").replace("http://", "").rstrip("/")
        self.base = f"https://{dsn}/api/v1" if dsn else ""
        self.account_id = config.UNIPILE_ACCOUNT_ID
        # linkedin_url -> {provider_id, network_distance}
        self._profile_cache: dict[str, dict] = {}

    # -- config / health ----------------------------------------------------
    def health_check(self) -> tuple[bool, str]:
        missing = [n for n, v in (("UNIPILE_DSN", self.base), ("UNIPILE_API_KEY", self.api_key),
                                  ("UNIPILE_ACCOUNT_ID", self.account_id)) if not v]
        if missing:
            return False, f"not configured: {', '.join(missing)}"
        return True, "unipile configured"

    def _acct(self, account: LinkedInAccount) -> str:
        return account.provider_account_id or self.account_id

    def _headers(self, json_body: bool = True) -> dict:
        if not self.api_key or not self.base:
            raise UnipileError("Unipile is not configured (UNIPILE_DSN / UNIPILE_API_KEY).")
        h = {"X-API-KEY": self.api_key, "Accept": "application/json"}
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    @staticmethod
    def _public_id(linkedin_url: str) -> str:
        m = _SLUG_RE.search(linkedin_url or "")
        return m.group(1) if m else linkedin_url.strip("/").split("/")[-1]

    # -- profile resolution -------------------------------------------------
    def _profile(self, account: LinkedInAccount, linkedin_url: str) -> dict:
        """Resolve + cache {provider_id, network_distance} for a profile URL."""
        if linkedin_url in self._profile_cache:
            return self._profile_cache[linkedin_url]
        identifier = self._public_id(linkedin_url)
        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{self.base}/users/{identifier}",
                           headers=self._headers(json_body=False),
                           params={"account_id": self._acct(account)})
            r.raise_for_status()
            data = r.json() or {}
        info = {
            "provider_id": data.get("provider_id") or data.get("id") or "",
            "network_distance": str(data.get("network_distance")
                                    or data.get("network_distance_status") or ""),
        }
        if info["provider_id"]:
            self._profile_cache[linkedin_url] = info
        return info

    # -- provider interface -------------------------------------------------
    def send_invite(self, account: LinkedInAccount, linkedin_url: str, note: str) -> ActionResult:
        try:
            provider_id = self._profile(account, linkedin_url).get("provider_id")
            if not provider_id:
                return ActionResult(ok=False, error=f"could not resolve provider_id for {linkedin_url}")
            body = {"account_id": self._acct(account), "provider_id": provider_id}
            if note:
                body["message"] = note[:200]
            with httpx.Client(timeout=30.0) as client:
                r = client.post(f"{self.base}/users/invite", headers=self._headers(), json=body)
                r.raise_for_status()
        except (httpx.HTTPError, UnipileError) as exc:
            return ActionResult(ok=False, error=f"invite failed: {exc}")
        return ActionResult(ok=True, provider_ref=provider_id)

    def send_message(self, account: LinkedInAccount, linkedin_url: str, text: str) -> ActionResult:
        try:
            provider_id = self._profile(account, linkedin_url).get("provider_id")
            if not provider_id:
                return ActionResult(ok=False, error=f"could not resolve provider_id for {linkedin_url}")
            form = {"account_id": self._acct(account), "attendees_ids": provider_id,
                    "text": text, "linkedin[api]": "classic"}
            with httpx.Client(timeout=30.0) as client:
                r = client.post(f"{self.base}/chats", headers=self._headers(json_body=False), data=form)
                r.raise_for_status()
                data = r.json() or {}
        except (httpx.HTTPError, UnipileError) as exc:
            return ActionResult(ok=False, error=f"message failed: {exc}")
        chat_id = data.get("chat_id") or data.get("id") or provider_id
        return ActionResult(ok=True, provider_ref=str(chat_id))

    def fetch_accepted(self, account: LinkedInAccount, linkedin_urls: list[str]) -> set[str]:
        accepted: set[str] = set()
        for url in linkedin_urls:
            self._profile_cache.pop(url, None)  # force a fresh read
            try:
                dist = self._profile(account, url).get("network_distance", "").upper()
            except (httpx.HTTPError, UnipileError) as exc:
                logger.warning("accepted check failed for %s: %s", url, exc)
                continue
            if "DISTANCE_1" in dist or "FIRST" in dist or dist == "1":
                accepted.add(url)
        return accepted

    def fetch_replies(self, account: LinkedInAccount, since_iso: str) -> list[InboundMessage]:
        """Return inbound messages from UNREAD chats only.

        Filtering to unread keeps this fast on busy inboxes (100 chats → a few)
        and naturally targets new replies; message-id dedupe upstream prevents
        reprocessing. The other party is identified by ``attendee_provider_id``,
        which we resolve back to a profile URL so the dispatcher can match it.
        """
        out: list[InboundMessage] = []
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.get(f"{self.base}/chats", headers=self._headers(json_body=False),
                               params={"account_id": self._acct(account)})
                r.raise_for_status()
                chats = (r.json() or {}).get("items", [])
                unread = [c for c in chats if c.get("unread") or c.get("unread_count")]
                logger.info("Unipile: %d chats, %d unread", len(chats), len(unread))
                for chat in unread:
                    chat_id = chat.get("id") or chat.get("chat_id")
                    pid = chat.get("attendee_provider_id", "")
                    if not chat_id:
                        continue
                    url = self._url_for_pid(client, account, pid)
                    if not url:
                        continue
                    mr = client.get(f"{self.base}/chats/{chat_id}/messages",
                                    headers=self._headers(json_body=False))
                    if mr.status_code != 200:
                        continue
                    for msg in (mr.json() or {}).get("items", []):
                        if msg.get("is_sender") or not msg.get("text"):
                            continue  # our own outbound / empty
                        out.append(InboundMessage(
                            linkedin_url=url,
                            provider_id=str(msg.get("id") or f"{chat_id}:{msg.get('timestamp')}"),
                            text=msg.get("text") or "",
                            received_at=str(msg.get("timestamp") or utcnow_iso())))
        except (httpx.HTTPError, UnipileError) as exc:
            logger.warning("fetch_replies failed: %s", exc)
        return out

    def _url_for_pid(self, client: httpx.Client, account: LinkedInAccount, provider_id: str) -> str:
        """Resolve an ``attendee_provider_id`` to a LinkedIn profile URL (cached)."""
        if not provider_id:
            return ""
        cached = self._profile_cache.get("pid:" + provider_id)
        if cached:
            return cached["provider_id"]  # reuse the dict slot to store the url
        try:
            r = client.get(f"{self.base}/users/{provider_id}",
                           headers=self._headers(json_body=False),
                           params={"account_id": self._acct(account)})
            r.raise_for_status()
            data = r.json() or {}
        except httpx.HTTPError:
            return ""
        public_id = data.get("public_identifier") or data.get("public_id") or ""
        url = f"https://www.linkedin.com/in/{public_id}" if public_id else ""
        if url:
            self._profile_cache["pid:" + provider_id] = {"provider_id": url}
        return url
