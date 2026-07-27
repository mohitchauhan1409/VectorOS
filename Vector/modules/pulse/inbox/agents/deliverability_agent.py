"""DeliverabilityGuardian — preflight checks before a campaign sends.

With a self-built (free) engine, deliverability is yours to protect. This runs
two deterministic, zero-cost checks:

  1. COPY scan — spam-trigger words, link overload, ALL-CAPS shouting, exclamation
     spam, risky subject lines. Catches content that lands in spam.
  2. DNS auth — SPF, DMARC, and (best-effort) DKIM records on each sending
     domain. Missing auth is the single biggest reason cold email bounces or
     spam-folders. Uses ``dnspython`` (already a project dependency).

No LLM, no API, no cost. It returns findings; it never blocks — the caller
decides whether to proceed.
"""

from __future__ import annotations

import re

import dns.resolver

from modules.common.logger import get_logger
from modules.pulse.inbox import store

logger = get_logger("pulse.inbox.deliverability")

# Classic spam-filter trigger phrases (lowercased substring match).
SPAM_TRIGGERS = (
    "free", "guarantee", "guaranteed", "no obligation", "risk-free", "act now",
    "limited time", "urgent", "winner", "congratulations", "cash", "cheap",
    "click here", "buy now", "order now", "100%", "$$$", "earn money",
    "make money", "income", "investment", "credit card", "prize", "offer expires",
    "increase sales", "double your", "best price", "lowest price", "discount",
)

# Common DKIM selectors to probe (we can't know the real one without the domain's help).
DKIM_SELECTORS = ("google", "default", "selector1", "selector2", "k1", "s1", "mail", "dkim")

_LINK_RE = re.compile(r"https?://", re.IGNORECASE)
_CAPS_WORD_RE = re.compile(r"\b[A-Z]{4,}\b")


class DeliverabilityGuardian:
    """Preflight deliverability checks. Deterministic; safe to run anytime."""

    def __init__(self, dns_timeout: float = 5.0) -> None:
        self._resolver = dns.resolver.Resolver()
        self._resolver.lifetime = dns_timeout
        self._resolver.timeout = dns_timeout

    # -- copy -------------------------------------------------------------
    def scan_copy(self, subject: str, body: str) -> list[dict]:
        """Return content warnings for one email (empty list = clean)."""
        warnings: list[dict] = []
        text = f"{subject}\n{body}"
        low = text.lower()

        hits = sorted({w for w in SPAM_TRIGGERS if w in low})
        if hits:
            warnings.append({"level": "warn", "check": "spam_words",
                             "detail": f"spam-trigger phrases: {', '.join(hits)}"})

        links = len(_LINK_RE.findall(body))
        if links > 2:
            warnings.append({"level": "warn", "check": "links",
                             "detail": f"{links} links — cold emails do best with 0-1"})

        caps = _CAPS_WORD_RE.findall(text)
        if len(caps) >= 2:
            warnings.append({"level": "warn", "check": "all_caps",
                             "detail": f"ALL-CAPS words: {', '.join(caps[:5])}"})

        bangs = text.count("!")
        if bangs >= 2:
            warnings.append({"level": "warn", "check": "exclamations",
                             "detail": f"{bangs} exclamation marks — reads as salesy"})

        if len(subject) > 60:
            warnings.append({"level": "info", "check": "subject_len",
                             "detail": f"subject is {len(subject)} chars — under ~50 lands better"})

        words = len(re.findall(r"\w+", body))
        if words > 200:
            warnings.append({"level": "info", "check": "length",
                             "detail": f"{words} words — cold emails convert best under ~125"})
        elif words < 15:
            warnings.append({"level": "info", "check": "length",
                             "detail": f"only {words} words — may look thin/templated"})
        return warnings

    # -- DNS auth ---------------------------------------------------------
    def _txt(self, name: str) -> list[str]:
        try:
            answers = self._resolver.resolve(name, "TXT")
            return ["".join(s.decode() if isinstance(s, bytes) else s for s in r.strings)
                    for r in answers]
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers,
                dns.exception.Timeout, dns.resolver.LifetimeTimeout):
            return []

    def check_dns(self, domain: str) -> dict:
        """Check SPF / DMARC / DKIM for a sending domain."""
        spf = [t for t in self._txt(domain) if t.lower().startswith("v=spf1")]
        dmarc = [t for t in self._txt(f"_dmarc.{domain}") if "v=dmarc1" in t.lower()]
        dkim_selector = None
        for sel in DKIM_SELECTORS:
            recs = self._txt(f"{sel}._domainkey.{domain}")
            if any("v=dkim1" in r.lower() or "p=" in r.lower() for r in recs):
                dkim_selector = sel
                break
        return {
            "domain": domain,
            "spf": bool(spf),
            "spf_record": spf[0] if spf else "",
            "dmarc": bool(dmarc),
            "dmarc_record": dmarc[0] if dmarc else "",
            "dkim": dkim_selector is not None,
            "dkim_selector": dkim_selector or "",
        }

    # -- preflight --------------------------------------------------------
    def preflight(self, sample: tuple[str, str] | None = None) -> dict:
        """Check every active mailbox's domain + optionally scan a sample email.

        ``sample`` is an optional ``(subject, body)`` to scan. Returns a report
        with a top-level ``ok`` flag (False if any hard auth record is missing).
        """
        report: dict = {"domains": [], "copy_warnings": [], "ok": True}
        seen: set[str] = set()
        for mb in store.list_mailboxes(active_only=True):
            domain = mb.email.split("@")[-1].lower()
            if domain in seen:
                continue
            seen.add(domain)
            dns_res = self.check_dns(domain)
            if not (dns_res["spf"] and dns_res["dmarc"]):
                report["ok"] = False
            report["domains"].append(dns_res)

        if sample is not None:
            report["copy_warnings"] = self.scan_copy(sample[0], sample[1])
        logger.info("Preflight: %d domain(s) checked, ok=%s", len(report["domains"]), report["ok"])
        return report
