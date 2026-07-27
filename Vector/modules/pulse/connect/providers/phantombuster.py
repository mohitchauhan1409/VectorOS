"""PhantomBusterProvider — real LinkedIn transport via PhantomBuster's cloud API.

PhantomBuster runs pre-configured "Phantoms" (each wired once in their UI with
your LinkedIn session cookie) on their own cloud + proxies — so we never run raw
cookie automation ourselves; PhantomBuster carries the ban-risk engineering.
Its free tier includes API access, enough for demos.

The API is launch-and-poll (async containers), not a per-action REST API:
    POST /agents/launch            {id, argument}     -> {containerId}
    GET  /containers/fetch          ?id=<container>    -> {status: running|finished}
    GET  /containers/fetch-result-object ?id=<c>       -> {resultObject: "<json>"}
Auth header: ``X-Phantombuster-Key``.

You create four Phantoms in the UI and put their agent ids in the env
(see .env.example): Auto Connect, Message Sender, Profile Scraper (for
connection-degree = acceptance detection), and Inbox/Message extractor (replies).

Because each Phantom's exact input/output columns vary by version, the argument
builders below use the common field names and the result parsing is defensive;
adjust ``_connect_argument`` etc. to match your Phantoms if needed.
"""

from __future__ import annotations

import json
import time

import httpx

from modules.common.logger import get_logger
from modules.pulse.connect import config
from modules.pulse.connect.schemas import ActionResult, InboundMessage, LinkedInAccount, utcnow_iso

logger = get_logger("pulse.connect.phantombuster")


class PhantomBusterError(RuntimeError):
    pass


class PhantomBusterProvider:
    name = "phantombuster"

    def __init__(self) -> None:
        self.api_key = config.PB_API_KEY
        self.base = config.PB_BASE_URL.rstrip("/")
        self.session_cookie = config.PB_SESSION_COOKIE
        self.user_agent = config.PB_USER_AGENT
        self.timeout = config.PB_LAUNCH_TIMEOUT

    # -- config / health ----------------------------------------------------
    def health_check(self) -> tuple[bool, str]:
        missing = [n for n, v in (("PHANTOMBUSTER_API_KEY", self.api_key),
                                   ("PB_CONNECT_AGENT_ID", config.PB_CONNECT_AGENT_ID))
                   if not v]
        if missing:
            return False, f"not configured: {', '.join(missing)}"
        return True, "phantombuster configured"

    def _headers(self) -> dict:
        if not self.api_key:
            raise PhantomBusterError("PHANTOMBUSTER_API_KEY is not set.")
        return {"X-Phantombuster-Key": self.api_key, "Content-Type": "application/json"}

    # -- low-level launch + poll -------------------------------------------
    def _launch(self, agent_id: str, argument: dict) -> str:
        if not agent_id:
            raise PhantomBusterError("Missing PhantomBuster agent id for this action.")
        payload = {"id": agent_id, "argument": argument}
        with httpx.Client(timeout=30.0) as client:
            r = client.post(f"{self.base}/agents/launch", headers=self._headers(), json=payload)
            r.raise_for_status()
            data = r.json()
        container_id = data.get("containerId") or (data.get("data") or {}).get("containerId")
        if not container_id:
            raise PhantomBusterError(f"launch returned no containerId: {data}")
        return str(container_id)

    def _await_result(self, container_id: str) -> list[dict]:
        """Poll until the container finishes, then return its result rows."""
        deadline = self.timeout
        waited = 0.0
        with httpx.Client(timeout=30.0) as client:
            while waited < deadline:
                r = client.get(f"{self.base}/containers/fetch",
                               headers=self._headers(), params={"id": container_id})
                r.raise_for_status()
                status = (r.json() or {}).get("status", "")
                if status == "finished":
                    break
                time.sleep(5)
                waited += 5
            r = client.get(f"{self.base}/containers/fetch-result-object",
                           headers=self._headers(), params={"id": container_id})
            r.raise_for_status()
            result_obj = (r.json() or {}).get("resultObject")
        if not result_obj:
            return []
        try:
            parsed = json.loads(result_obj)
        except (ValueError, TypeError):
            return []
        return parsed if isinstance(parsed, list) else [parsed]

    def _session_args(self) -> dict:
        args: dict = {}
        if self.session_cookie:
            args["sessionCookie"] = self.session_cookie
        if self.user_agent:
            args["userAgent"] = self.user_agent
        return args

    # -- provider interface -------------------------------------------------
    def send_invite(self, account: LinkedInAccount, linkedin_url: str, note: str) -> ActionResult:
        arg = {**self._session_args(), "profileUrls": [linkedin_url],
               "message": note, "numberOfAddsPerLaunch": 1}
        try:
            container = self._launch(config.PB_CONNECT_AGENT_ID, arg)
        except (httpx.HTTPError, PhantomBusterError) as exc:
            return ActionResult(ok=False, error=f"invite failed: {exc}")
        return ActionResult(ok=True, provider_ref=f"container:{container}")

    def send_message(self, account: LinkedInAccount, linkedin_url: str, text: str) -> ActionResult:
        arg = {**self._session_args(), "profileUrls": [linkedin_url], "message": text}
        try:
            container = self._launch(config.PB_MESSAGE_AGENT_ID, arg)
        except (httpx.HTTPError, PhantomBusterError) as exc:
            return ActionResult(ok=False, error=f"message failed: {exc}")
        return ActionResult(ok=True, provider_ref=f"container:{container}")

    def fetch_accepted(self, account: LinkedInAccount, linkedin_urls: list[str]) -> set[str]:
        """Scrape the given profiles and keep those now at connection degree 1st."""
        if not linkedin_urls or not config.PB_PROFILE_AGENT_ID:
            return set()
        arg = {**self._session_args(), "profileUrls": linkedin_urls}
        try:
            rows = self._await_result(self._launch(config.PB_PROFILE_AGENT_ID, arg))
        except (httpx.HTTPError, PhantomBusterError) as exc:
            logger.warning("fetch_accepted failed: %s", exc)
            return set()
        accepted: set[str] = set()
        for row in rows:
            url = row.get("profileUrl") or row.get("linkedinUrl") or row.get("query") or ""
            degree = str(row.get("connectionDegree") or row.get("distance") or "").lower()
            if url and ("1st" in degree or "distance_1" in degree or degree == "1"):
                accepted.add(url)
        return accepted

    def fetch_replies(self, account: LinkedInAccount, since_iso: str) -> list[InboundMessage]:
        if not config.PB_INBOX_AGENT_ID:
            return []
        try:
            rows = self._await_result(self._launch(config.PB_INBOX_AGENT_ID, self._session_args()))
        except (httpx.HTTPError, PhantomBusterError) as exc:
            logger.warning("fetch_replies failed: %s", exc)
            return []
        out: list[InboundMessage] = []
        for row in rows:
            # Skip our own outbound messages.
            if row.get("isLastMessageFromMe") or row.get("fromMe"):
                continue
            text = row.get("message") or row.get("lastMessage") or row.get("text") or ""
            url = row.get("profileUrl") or row.get("senderUrl") or row.get("linkedinUrl") or ""
            ts = row.get("timestamp") or row.get("lastMessageDate") or utcnow_iso()
            mid = str(row.get("messageId") or row.get("threadId") or f"{url}:{ts}")
            if text and url and str(ts) >= since_iso[:len(str(ts))]:
                out.append(InboundMessage(linkedin_url=url, provider_id=mid, text=text,
                                          received_at=str(ts)))
        return out
