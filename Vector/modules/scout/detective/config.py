"""Detective configuration.

Detective finds the decision-makers at the companies Radar qualified, then
(optionally) enriches them via Apollo for contact data.

Cost discipline lives here: which roles we hunt, how many people per company,
and Apollo reveal flags (kept minimal to preserve trial credits).
"""

from __future__ import annotations

# Controlling knobs live in modules/common/control.py (single control panel).
# This file keeps only fixed endpoints; every toggle/threshold is sourced below.
from modules.common import control

# Decision-maker roles to search for, highest priority first.
TARGET_ROLES: tuple[str, ...] = control.DETECTIVE_TARGET_ROLES

# Title alone is ambiguous in payments: a "Chief Risk Officer" is as likely to own
# fraud and AML as merchant credit, and only one of those can buy from us. The
# profile agent scores candidates against these before accepting them.
ROLE_MUST_MATCH: tuple[str, ...] = control.DETECTIVE_ROLE_MUST_MATCH
ROLE_EXCLUDE: tuple[str, ...] = control.DETECTIVE_ROLE_EXCLUDE


def role_in_scope(text: str) -> bool:
    """True when a profile plausibly owns MERCHANT CREDIT risk.

    Evidence of credit/merchant scope wins outright — "Head of Credit Risk &
    Compliance" is a standard combined title at UK/EU EMIs and payment
    institutions, so a naive compliance veto would discard real buyers. The
    exclude list only vetoes profiles with no credit signal at all (a pure
    fraud/AML/financial-crime leader can't buy risk transfer).
    """
    t = (text or "").lower()
    if any(k in t for k in ROLE_MUST_MATCH):
        return True
    return not any(k in t for k in ROLE_EXCLUDE)

# Cap people per company so we don't fan out searches / burn Apollo credits.
MAX_DECISION_MAKERS_PER_COMPANY = control.DETECTIVE_MAX_DECISION_MAKERS_PER_COMPANY

# How many search results to inspect per role query.
RESULTS_PER_ROLE = control.DETECTIVE_RESULTS_PER_ROLE

# LLM tier for Detective's profile-extraction agent (cheap, high-volume triage).
NORMAL_LLM = control.NORMAL_LLM

# ---------------------------------------------------------------------------
# Email finding — provider + fallbacks (toggles live in control.py)
# ---------------------------------------------------------------------------
#   "pdl" | "apollo" | "none" (skip providers → pattern fallback)
EMAIL_PROVIDER = control.EMAIL_PROVIDER
EMAIL_PATTERN_FALLBACK = control.EMAIL_PATTERN_FALLBACK

# --- People Data Labs (person enrichment) ---
PDL_ENRICH_URL = "https://api.peopledatalabs.com/v5/person/enrich"
PDL_MIN_LIKELIHOOD = control.PDL_MIN_LIKELIHOOD

# --- Pattern generator + SMTP verification (keyless fallback) ---
SMTP_VERIFY = control.EMAIL_SMTP_VERIFY
SMTP_TIMEOUT = control.EMAIL_SMTP_TIMEOUT
SMTP_PROBE_FROM = control.EMAIL_SMTP_PROBE_FROM

# Extra keyless signals to pick the RIGHT address (esp. on catch-all domains).
EMAIL_WEB_INFERENCE = control.EMAIL_WEB_INFERENCE
EMAIL_GRAVATAR_CHECK = control.EMAIL_GRAVATAR_CHECK
INFERENCE_GRAVATAR_MAX_CHECKS = control.EMAIL_INFERENCE_GRAVATAR_MAX_CHECKS

# ---------------------------------------------------------------------------
# Apollo — credit-saving defaults
# ---------------------------------------------------------------------------
APOLLO_BULK_MATCH_URL = "https://api.apollo.io/api/v1/people/bulk_match"
APOLLO_MAX_BATCH = control.APOLLO_MAX_BATCH
APOLLO_REVEAL_PERSONAL_EMAILS = control.APOLLO_REVEAL_PERSONAL_EMAILS
APOLLO_REVEAL_PHONE_NUMBER = control.APOLLO_REVEAL_PHONE_NUMBER
