"""Keyless email finder: generate likely addresses, then confirm the RIGHT one
using every free signal available.

Signal precedence (strongest first):
  1. SMTP verified   — server accepted exactly this address (non-catch-all domain)
  2. web-confirmed    — the exact address was found on the web (team page, paper…)
  3. gravatar-confirmed — the address is a registered Gravatar account
  4. ranked guess     — best pattern by domain-format inference + statistics

The extra signals matter most on CATCH-ALL domains, where SMTP accepts every
address and can't tell which mailbox is real.

Never raises: degrades to a best-guess ranked list.
"""

from __future__ import annotations

import re
import smtplib
import unicodedata

from modules.common.logger import get_logger
from modules.scout.detective.config import (
    EMAIL_GRAVATAR_CHECK,
    EMAIL_WEB_INFERENCE,
    INFERENCE_GRAVATAR_MAX_CHECKS,
    SMTP_PROBE_FROM,
    SMTP_TIMEOUT,
    SMTP_VERIFY,
)
from modules.scout.detective.email.base import EmailProvider, EmailResult
from modules.scout.detective.email.inference import (
    gravatar_exists,
    harvest_domain_emails,
    infer_style,
)
from modules.scout.detective.schemas import DecisionMaker

logger = get_logger("detective.email.pattern")

_CATCH_ALL_PROBE = "zz9-no-such-user-42x"


def _ascii(text: str) -> str:
    """Fold to lowercase ascii letters (José -> jose)."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "".join(c for c in text.lower() if c.isalpha())


def _domain_from(domain: str | None) -> str | None:
    if not domain:
        return None
    d = domain.strip().lower().split("://")[-1].split("/")[0]
    return d.removeprefix("www.") or None


def candidate_emails(name: str, domain: str) -> list[str]:
    """Return likely email addresses for ``name`` at ``domain``, most-likely first."""
    parts = [p for p in name.split() if p]
    if len(parts) < 2:
        first = _ascii(parts[0]) if parts else ""
        return [f"{first}@{domain}"] if first else []
    first, last = _ascii(parts[0]), _ascii(parts[-1])
    if not first or not last:
        return []
    f = first[0]
    patterns = [
        f"{first}.{last}", f"{first}", f"{f}{last}", f"{first}{last}",
        f"{f}.{last}", f"{last}", f"{first}_{last}", f"{last}.{first}",
        f"{f}-{last}", f"{last}{f}",
    ]
    seen, out = set(), []
    for p in patterns:
        addr = f"{p}@{domain}"
        if addr not in seen:
            seen.add(addr)
            out.append(addr)
    return out


class PatternEmailProvider(EmailProvider):
    """Generates candidates, then confirms via SMTP / web / Gravatar."""

    name = "pattern"

    def find(self, person: DecisionMaker, domain: str | None) -> EmailResult | None:
        dom = _domain_from(domain)
        if not dom:
            return None
        candidates = candidate_emails(person.name, dom)
        if not candidates:
            return None

        # 1) SMTP probe — authoritative when usable and the domain isn't catch-all.
        state, verified = ("unusable", None)
        if SMTP_VERIFY:
            state, verified = self._smtp_probe(dom, candidates)
        if state == "verified" and verified:
            return EmailResult(verified, "verified", "pattern-smtp",
                               self._rank_first(verified, candidates))

        # 2/3/4) keyless inference (web harvest + gravatar) to pick the best.
        return self._rank_with_signals(person, dom, candidates, catchall=(state == "catchall"))

    # ---- keyless signal ranking ----
    def _rank_with_signals(
        self, person: DecisionMaker, domain: str, candidates: list[str], catchall: bool
    ) -> EmailResult:
        harvested: set[str] = set()
        style = {"dot": False, "first_only": False}

        if EMAIL_WEB_INFERENCE:
            harvested = harvest_domain_emails(domain, hints=[person.name])
            # Pull in real name-matching addresses even if we didn't generate them.
            tokens = [t for t in re.split(r"[^a-z]+", person.name.lower()) if len(t) > 2]
            for addr in harvested:
                local = addr.split("@")[0]
                if any(t in local for t in tokens) and addr not in candidates:
                    candidates.insert(0, addr)
            # Any candidate that appears verbatim on the web is a real address.
            web_hit = next((c for c in candidates if c in harvested), None)
            if web_hit:
                logger.info("Web-confirmed %s", web_hit)
                return EmailResult(web_hit, "verified", "pattern-web",
                                   self._rank_first(web_hit, candidates))
            style = infer_style([e.split("@")[0] for e in harvested])

        scored = self._score(candidates, style, harvested)

        # Gravatar: a hit proves the exact address is a real account (catch-all safe).
        if EMAIL_GRAVATAR_CHECK:
            for _, addr in scored[:INFERENCE_GRAVATAR_MAX_CHECKS]:
                if gravatar_exists(addr):
                    logger.info("Gravatar-confirmed %s", addr)
                    ranked = [addr] + [c for _, c in scored if c != addr]
                    return EmailResult(addr, "verified", "pattern-gravatar", ranked)

        ranked = [c for _, c in scored]
        status = "unverified" if catchall else "guessed"
        logger.info("No hard confirmation; best guess %s (%s)", ranked[0], status)
        return EmailResult(ranked[0], status, "pattern", ranked)

    @staticmethod
    def _score(candidates: list[str], style: dict, harvested: set[str]) -> list[tuple[int, str]]:
        scored: list[tuple[int, str]] = []
        n = len(candidates)
        for i, c in enumerate(candidates):
            local = c.split("@")[0]
            s = n - i  # statistical prior (earlier patterns are more common)
            if harvested and c in harvested:
                s += 1000
            if style.get("dot") and "." in local:
                s += 25
            if style.get("first_only") and local.isalpha() and len(local) <= 9:
                s += 25
            scored.append((s, c))
        scored.sort(key=lambda t: t[0], reverse=True)
        return scored

    @staticmethod
    def _rank_first(winner: str, candidates: list[str]) -> list[str]:
        return [winner] + [c for c in candidates if c != winner]

    # ---- SMTP ----
    def _smtp_probe(self, domain: str, candidates: list[str]) -> tuple[str, str | None]:
        """Return (state, verified_addr). state: verified|catchall|nomatch|unusable."""
        try:
            import dns.resolver

            answers = dns.resolver.resolve(domain, "MX")
            mx_host = str(sorted(answers, key=lambda r: r.preference)[0].exchange).rstrip(".")
        except Exception as exc:  # noqa: BLE001
            logger.info("MX lookup failed for %s: %s", domain, exc)
            return "unusable", None

        try:
            server = smtplib.SMTP(timeout=SMTP_TIMEOUT)
            server.connect(mx_host, 25)
            server.helo(server.local_hostname)
            server.mail(SMTP_PROBE_FROM)

            code, _ = server.rcpt(f"{_CATCH_ALL_PROBE}@{domain}")
            if code in (250, 251):
                server.quit()
                logger.info("%s is catch-all", domain)
                return "catchall", None

            for addr in candidates:
                code, _ = server.rcpt(addr)
                if code in (250, 251):
                    server.quit()
                    logger.info("SMTP verified %s", addr)
                    return "verified", addr
            server.quit()
            return "nomatch", None
        except (smtplib.SMTPException, OSError) as exc:
            logger.info("SMTP probe failed for %s (%s)", domain, exc)
            return "unusable", None
