"""Seed the demo workspace with a rich, realistic dataset.

This reproduces the CRM's sample data inside SQLite so the demo account
(login: demo@vector.ai) always shows a full pipeline, while every other
account starts empty and is populated by live engine runs.

Deterministic (seeded RNG) so the demo looks identical on every rebuild.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import (
    Campaign,
    Company,
    ContactMeeting,
    Deal,
    DealHighlight,
    DealNextStep,
    Enrollment,
    MeetingPoint,
    Event,
    ICPCriterion,
    Message,
    Person,
    Sequence,
    SequenceStep,
    Signal,
    Sponsorship,
    User,
    Variant,
    Workspace,
)
from backend.security import hash_password

DEMO_EMAIL = "demo@vector.ai"
DEMO_PASSWORD = "demo1234"
BASE = datetime(2026, 7, 22, 9, 0, 0, tzinfo=timezone.utc)

# --- seeded RNG (mulberry32, mirrors the frontend) ---
_state = 0x51EE7A1


def _reset(n: int = 0x51EE7A1) -> None:
    global _state
    _state = n


def rand() -> float:
    global _state
    _state = (_state + 0x6D2B79F5) & 0xFFFFFFFF
    t = _state
    t = (t ^ (t >> 15)) * (1 | t) & 0xFFFFFFFF
    t = (t + ((t ^ (t >> 7)) * (61 | t) & 0xFFFFFFFF)) & 0xFFFFFFFF ^ t
    return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296


def randint(a: int, b: int) -> int:
    return int(rand() * (b - a + 1)) + a


def pick(arr):
    return arr[int(rand() * len(arr))]


def pick_n(arr, n):
    copy = list(arr)
    out = []
    for _ in range(min(n, len(copy))):
        out.append(copy.pop(int(rand() * len(copy))))
    return out


def chance(p: float) -> bool:
    return rand() < p


def days_ago(days: float) -> datetime:
    return BASE - timedelta(days=days, hours=randint(0, 20))


def human_date(days: float) -> str:
    return (BASE - timedelta(days=days)).strftime("%b %-d, %Y")


# ---------------------------------------------------------------------------
# Konfyd's market: payment processors, PSPs, acquirers, payfacs and platforms
# that carry merchant credit risk. Real companies, real categories — so the
# demo reads like a genuine acquiring pipeline rather than filler.
# (name, slug, domain, industry, employees, location)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Konfyd's market. The dominant segmentation axis is NOT industry label — it's
# who legally carries the merchant credit risk:
#
#   principal    — a principal scheme member. Liable to Visa/Mastercard for every
#                  merchant on the book. Sets its own reserve policy. Best buyer.
#   sponsor_bank  — sponsors payfacs/PSPs onto the schemes. Carries residual on
#                  every entity it sponsors and prices it with a blanket
#                  collateral formula because it can't see the sub-merchant book.
#                  One relationship opens a portfolio of sponsored entities.
#   sponsored    — payfac / PSP operating under someone else's membership. Feels
#                  the loss through the sponsorship agreement but often can't
#                  change its own reserve. Sellable, different pitch.
#   none         — routes volume or sells software but never carries settlement
#                  risk (orchestration, gateways, billing, issuing). Not a buyer.
#
# `deferred` flags books with heavy paid-but-undelivered exposure (travel,
# ticketing, events, subscriptions) — where merchant insolvency is catastrophic
# rather than merely expensive. `buyable` is whether they could realistically
# sign with an early-stage counterparty at all.
#
# (name, slug, domain, industry, employees, location, risk_carrier, deferred, buyable)
# ---------------------------------------------------------------------------
COMPANY_SEEDS = [
    # --- High-risk / deferred-delivery specialist acquirers: the sweet spot ---
    ("PXP Financial", "pxp-financial", "pxpfinancial.com", "High-Risk Acquiring", "201-1000", "London, UK", "principal", True, True),
    ("Emerchantpay", "emerchantpay", "emerchantpay.com", "High-Risk Acquiring", "201-1000", "London, UK", "principal", True, True),
    ("Trust Payments", "trust-payments", "trustpayments.com", "High-Risk Acquiring", "201-1000", "London, UK", "principal", True, True),
    ("Maverick Payments", "maverick-payments", "maverickpayments.com", "High-Risk Acquiring", "51-200", "Calabasas, US", "sponsored", True, True),
    ("PaymentCloud", "paymentcloud", "paymentcloudinc.com", "High-Risk Acquiring", "51-200", "Sherman Oaks, US", "sponsored", True, True),
    ("Corepay", "corepay", "corepay.net", "High-Risk Acquiring", "11-50", "Fort Lauderdale, US", "sponsored", True, True),
    ("Segpay", "segpay", "segpay.com", "High-Risk Acquiring", "51-200", "Boca Raton, US", "sponsored", True, True),
    ("Praxis Tech", "praxis-tech", "praxispay.com", "High-Risk Acquiring", "51-200", "Limassol, EU", "sponsored", True, True),
    ("Zen.com", "zen-com", "zen.com", "High-Risk Acquiring", "201-1000", "Vilnius, EU", "principal", True, True),

    # --- Travel / ticketing acquirers: deferred delivery IS the business ---
    ("Trust My Travel", "trust-my-travel", "trustmytravel.com", "Travel Acquiring", "11-50", "Bristol, UK", "sponsored", True, True),
    ("Outpayce by Amadeus", "outpayce", "outpayce.com", "Travel Acquiring", "201-1000", "Madrid, EU", "principal", True, True),
    ("Ratepay", "ratepay", "ratepay.com", "Deferred-Payment Acquiring", "201-1000", "Berlin, EU", "principal", True, True),

    # --- Mid-market principal processors / acquirers ---
    ("Nuvei", "nuvei", "nuvei.com", "Payment Processor", "1001-5000", "Montreal, CA", "principal", True, True),
    ("Paysafe", "paysafe", "paysafe.com", "Payment Processor", "1001-5000", "London, UK", "principal", True, True),
    ("Shift4", "shift4", "shift4.com", "Payment Processor", "1001-5000", "Allentown, US", "principal", True, True),
    ("Priority Technology", "priority", "prioritycommerce.com", "Merchant Acquirer", "1001-5000", "Alpharetta, US", "principal", False, True),
    ("BlueSnap", "bluesnap", "bluesnap.com", "Payment Service Provider", "201-1000", "Waltham, US", "principal", True, True),
    ("Checkout.com", "checkout-com", "checkout.com", "Payment Service Provider", "1001-5000", "London, UK", "principal", True, True),
    ("dLocal", "dlocal", "dlocal.com", "Cross-Border Acquiring", "1001-5000", "Montevideo, UY", "principal", True, True),
    ("EBANX", "ebanx", "ebanx.com", "Cross-Border Acquiring", "1001-5000", "Curitiba, BR", "principal", True, True),
    ("Rapyd", "rapyd", "rapyd.net", "Payment Service Provider", "1001-5000", "London, UK", "principal", True, True),
    ("Stax Payments", "stax", "staxpayments.com", "Payment Processor", "201-1000", "Orlando, US", "sponsored", False, True),
    ("Mollie", "mollie", "mollie.com", "Payment Service Provider", "201-1000", "Amsterdam, EU", "principal", False, True),
    ("PayU GPO", "payu-gpo", "payu.com", "Emerging-Market Acquiring", "1001-5000", "Amsterdam, EU", "principal", True, True),
    ("Worldpay", "worldpay", "worldpay.com", "Merchant Acquirer", "5000+", "Cincinnati, US", "principal", True, False),
    ("Elavon", "elavon", "elavon.com", "Merchant Acquirer", "5000+", "Atlanta, US", "principal", True, False),

    # --- Sponsor / BIN-sponsoring banks: they carry residual on every payfac ---
    ("Esquire Financial", "esquire-financial", "esquirebank.com", "Sponsor Bank", "201-1000", "Jericho, US", "sponsor_bank", True, True),
    ("Merrick Bank", "merrick-bank", "merrickbank.com", "Sponsor Bank", "201-1000", "South Jordan, US", "sponsor_bank", True, True),
    ("Pathward", "pathward", "pathward.com", "Sponsor Bank", "1001-5000", "Sioux Falls, US", "sponsor_bank", True, True),
    ("Cross River Bank", "cross-river", "crossriver.com", "Sponsor Bank", "1001-5000", "Fort Lee, US", "sponsor_bank", True, True),
    ("Celtic Bank", "celtic-bank", "celticbank.com", "Sponsor Bank", "201-1000", "Salt Lake City, US", "sponsor_bank", False, True),
    ("Metropolitan Commercial", "metropolitan", "mcbankny.com", "Sponsor Bank", "201-1000", "New York, US", "sponsor_bank", False, True),
    ("Woodforest National", "woodforest", "woodforest.com", "Sponsor Bank", "1001-5000", "The Woodlands, US", "sponsor_bank", False, True),
    ("Banking Circle", "banking-circle", "bankingcircle.com", "Sponsor Bank", "201-1000", "Luxembourg, EU", "sponsor_bank", True, True),
    ("Clear Junction", "clear-junction", "clearjunction.com", "Sponsor Bank", "51-200", "London, UK", "sponsor_bank", True, True),

    # --- Payfacs / payfac-as-a-service: sponsored, underwrite sub-merchants ---
    ("Finix", "finix", "finix.com", "Payfac-as-a-Service", "201-1000", "San Francisco, US", "sponsored", True, True),
    ("Tilled", "tilled", "tilled.com", "Payfac-as-a-Service", "51-200", "Boulder, US", "sponsored", False, True),
    ("Nexio", "nexio", "nexio.com", "Payfac-as-a-Service", "51-200", "Salt Lake City, US", "sponsored", False, True),
    ("Fortis", "fortis", "fortispay.com", "Payfac-as-a-Service", "201-1000", "Novi, US", "sponsored", True, True),
    ("SumUp", "sumup", "sumup.com", "Payfac / SMB Acquiring", "1001-5000", "London, UK", "principal", False, True),

    # --- Mid-market ISOs / portfolio owners ---
    ("North American Bancard", "nab", "nabancard.com", "ISO / Portfolio Owner", "1001-5000", "Troy, US", "sponsored", False, True),
    ("Electronic Merchant Systems", "ems", "emscorporate.com", "ISO / Portfolio Owner", "201-1000", "Cleveland, US", "sponsored", True, True),
    ("Xplor Pay", "xplor-pay", "xplorpay.com", "ISO / Portfolio Owner", "201-1000", "Atlanta, US", "sponsored", True, True),
    ("Merchant Industry", "merchant-industry", "merchantindustry.com", "ISO / Portfolio Owner", "51-200", "Long Island City, US", "sponsored", False, True),

    # --- Structurally poor fit: kept deliberately so the engine can show its
    #     reasoning by scoring them DOWN, not by omitting them. Primer is an
    #     active (correctly stalled) deal for exactly this reason.
    ("Primer", "primer", "primer.io", "Payment Orchestration", "51-200", "London, UK", "none", False, True),
    ("Spreedly", "spreedly", "spreedly.com", "Payment Orchestration", "51-200", "Durham, US", "none", False, True),
    ("Adyen", "adyen", "adyen.com", "Merchant Acquirer", "5000+", "Amsterdam, EU", "principal", True, False),
]

# Who sponsors whom. This is the edge that turns nine sponsor-bank accounts into a
# portfolio play: Esquire sponsors Maverick and Corepay, both already in pipeline,
# so one conversation at Esquire moves the collateral formula for both — and
# answers Tilled's blocker ("can Tilled change its own reserve?") upstream.
SPONSORSHIP: dict[str, tuple[str, ...]] = {
    "esquire-financial": ("maverick-payments", "corepay", "paymentcloud"),
    "merrick-bank": ("segpay", "merchant-industry"),
    "pathward": ("tilled", "nexio"),
    "cross-river": ("finix",),
    "celtic-bank": ("fortis",),
    "metropolitan": ("ems",),
    "woodforest": ("nab", "xplor-pay"),
    "banking-circle": ("praxis-tech", "zen-com"),
    "clear-junction": ("trust-my-travel",),
}

# Distinct pools for the randomly-generated contacts. The named people in
# DEAL_SEEDS are kept out of these so nobody appears twice in the workspace.
FIRST_NAMES = ["Marcus", "Elena", "Nadia", "Rachel", "Omar", "Hannah", "Yuki", "Ravi", "Clara", "Fatima", "Grace", "Ines", "Ali", "Julia", "Maya", "Nora", "Camille", "Dmitri", "Amara", "Henrik", "Beatriz", "Samir", "Lena", "Owen", "Farida", "Gerald", "Ingrid", "Rohan", "Sinead", "Tobias", "Valeria", "Yusuf", "Bridget", "Callum", "Delphine", "Emeka", "Franziska", "Gustavo", "Halima", "Iain"]
LAST_NAMES = ["Okonkwo", "Lindqvist", "Kowalski", "Mbeki", "Nguyen", "Rossi", "Andersson", "Silva", "Müller", "Hassan", "Dubois", "Tanaka", "Novak", "Reddy", "Bianchi", "Schneider", "Costa", "Larsson", "Bennett", "Frost", "Haas", "Rahman", "Petrov", "Vasquez", "Osei", "Lund", "Marchetti", "Sato", "Vidal", "Achebe", "Brennan", "Castellano", "Dvorak", "Eriksen", "Fitzgerald", "Grimaldi", "Halvorsen", "Ibrahim", "Janssen", "Kovac"]

# Konfyd sells to risk, credit and treasury. Ordered by who actually owns the
# decision — Commercial roles are allies, not buyers, so they sit last.
ROLES = [
    "Chief Risk Officer", "Head of Merchant Risk", "VP Underwriting",
    "Chief Credit Officer", "Treasurer", "Chief Financial Officer",
    "Head of Portfolio Risk", "Head of Merchant Acquiring",
]
TITLE_BY_ROLE = {
    "Chief Risk Officer": ["Chief Risk Officer", "Group Chief Risk Officer", "SVP & Chief Risk Officer"],
    "Head of Merchant Risk": ["Head of Merchant Risk", "Director of Merchant Credit Risk", "Head of Merchant Risk & Portfolio"],
    "VP Underwriting": ["VP Merchant Underwriting", "VP Merchant Risk & Underwriting", "Head of Underwriting"],
    "Chief Credit Officer": ["Chief Credit Officer", "Head of Credit Risk", "SVP Credit Risk"],
    "Treasurer": ["Group Treasurer", "Head of Treasury", "Head of Capital Markets"],
    "Chief Financial Officer": ["Chief Financial Officer", "CFO", "Deputy CFO"],
    "Head of Portfolio Risk": ["Head of Portfolio Risk", "Head of Settlement Risk", "Director of Merchant Financial Risk"],
    "Head of Merchant Acquiring": ["Head of Merchant Acquiring", "SVP Acquiring", "Director of Acquiring"],
}
# Small sponsored shops have no CRO — the founder/COO owns risk appetite.
SMALL_COMPANY_ROLES = ["Chief Executive Officer", "Chief Operating Officer"]

# A sponsor bank's org chart looks nothing like a processor's: the Chief Credit
# Officer chairs the committee, and sponsorship sits under its own head. Nobody
# there has the title "Head of Merchant Acquiring".
ROLES_BY_CARRIER = {
    "sponsor_bank": ["Chief Credit Officer", "Head of Merchant Sponsorship",
                     "Head of Payments Risk", "Chief Risk Officer", "Treasurer"],
}
TITLE_BY_ROLE["Head of Merchant Sponsorship"] = [
    "Head of Merchant Sponsorship", "SVP Payments & Sponsorship", "Director of BIN Sponsorship",
]
TITLE_BY_ROLE["Head of Payments Risk"] = [
    "Head of Payments Risk", "Director of Payments Risk", "SVP Payments Risk & Oversight",
]
TITLE_BY_ROLE["Chief Executive Officer"] = ["Co-Founder & CEO", "CEO", "Founder & CEO"]
TITLE_BY_ROLE["Chief Operating Officer"] = ["Chief Operating Officer", "COO", "VP Operations & Risk"]

SIGNAL_TYPES = ["funding", "expansion", "hiring", "product_launch", "leadership_hire", "merger_acquisition", "partnership", "award_recognition"]

# Where a signal came from — used to build a plausible article URL per source.
SOURCE_DOMAINS = {
    "Digital Transactions": "digitaltransactions.net",
    "PYMNTS": "pymnts.com",
    "Payments Dive": "paymentsdive.com",
    "Finextra": "finextra.com",
    "Fintech Futures": "fintechfutures.com",
    "FinSMEs": "finsmes.com",
    "SEC EDGAR": "sec.gov",
    "Visa Business News": "usa.visa.com",
}
SOURCES = list(SOURCE_DOMAINS)
EMAIL_SOURCES = ["pdl", "apollo", "pattern", "pattern-smtp", "pattern-gravatar"]

# ---------------------------------------------------------------------------
# Deterministic ICP scoring. The score has to be defensible line by line —
# a random number is the fastest way to lose a risk buyer's trust.
# ---------------------------------------------------------------------------
RISK_CARRIER_POINTS = {"principal": 40, "sponsor_bank": 38, "sponsored": 24, "none": 4}
SIGNAL_POINTS = {
    "merger_acquisition": 12,   # inherited a book they didn't underwrite
    "leadership_hire": 11,      # new risk leader rewriting reserve policy
    "product_launch": 10,       # payfac / embedded launch → new sub-merchant risk
    "expansion": 9,             # new geography, no loss history
    "funding": 8,               # growth targets meet capital limits
    "hiring": 7,                # scaling underwriting by headcount
    "partnership": 5,
    "award_recognition": 2,
}
SIZE_POINTS = {"11-50": 4, "51-200": 12, "201-1000": 15, "1001-5000": 13, "5000+": 6}


def _icp_score(risk_carrier: str, deferred: bool, buyable: bool, employees: str) -> int:
    """FIT: structural, durable, and deliberately free of any timing input.

    Whether a company can buy from Konfyd is a fact about its business model, not
    about what happened to it last week. Timing lives in `_intent_score`.
    """
    score = RISK_CARRIER_POINTS.get(risk_carrier, 4)
    score += 18 if deferred else 0          # deferred delivery is the killer exposure
    score += SIZE_POINTS.get(employees, 8)
    score += 12 if buyable else -22         # can they sign with an early-stage counterparty
    # Not carrying settlement risk is a STRUCTURAL disqualifier, not a deduction —
    # no amount of size or timing makes an orchestration layer a buyer. Capped
    # below MIN_ICP_SCORE (35) so it can never qualify.
    if risk_carrier == "none":
        return min(score, 28)
    # Too small to absorb a facility at all — same hard-cap logic.
    if employees == "11-50" and risk_carrier != "sponsor_bank":
        return min(score, 62)
    return max(4, min(97, score))


def _intent_score(signal: str, age_days: int) -> int:
    """INTENT: is there a reason to call THIS week. Decays with signal age.

    Half-life of 30 days — a portfolio acquisition is a live trigger for about a
    quarter, then it's just history. Separating this from fit is what lets the UI
    say "Fit 88 / Intent 12, last signal 41 days ago" instead of averaging the two
    into a number that means neither.
    """
    base = SIGNAL_POINTS.get(signal, 3) * 8      # 16-96 at day zero
    decay = 0.5 ** (max(0, age_days) / 30.0)
    return max(2, min(99, round(base * decay)))


def _icp_reasoning(name, industry, risk_carrier, deferred, buyable, employees, signal):
    """Return (rationale, matched_criteria, concerns) derived from the same
    attributes that produced the score — so the narrative can't contradict it."""
    matched, concerns = [], []

    if risk_carrier == "principal":
        matched.append("Principal scheme member — liable to the networks for every merchant on the book, "
                       "and sets its own reserve policy")
    elif risk_carrier == "sponsor_bank":
        matched.append("Sponsors payfacs and PSPs onto the schemes, carrying residual risk on every "
                       "entity it sponsors")
        matched.append("Prices sponsored-entity risk with a blanket collateral formula — no visibility "
                       "into the sub-merchant book")
    elif risk_carrier == "sponsored":
        matched.append("Underwrites sub-merchants at volume and absorbs their defaults through the "
                       "sponsorship agreement")
        concerns.append("Sponsor bank may set the reserve requirement, so the decision could sit "
                        "upstream rather than with them")
    else:
        concerns.append("Routes or enables volume without taking settlement risk — merchant credit "
                        "exposure sits with the acquirers behind them, not here")
        concerns.append("Better suited as a channel into its acquirer network than as a direct buyer")

    if deferred:
        matched.append("Heavy deferred-delivery exposure (travel, ticketing, events or subscriptions) "
                       "where a single insolvency crystallises months of forward bookings")
    else:
        concerns.append("Largely card-present or immediate-delivery mix, so tail exposure per merchant "
                        "is lower")

    if employees in ("51-200", "201-1000"):
        matched.append("Large enough to feel the capital cost, small enough to decide in a quarter")
    if not buyable:
        concerns.append("Scale and existing balance-sheet capacity make third-party risk transfer from "
                        "an early-stage counterparty unlikely")

    verdict = ("a strong fit" if risk_carrier in ("principal", "sponsor_bank") and deferred and buyable
               else "a workable fit" if risk_carrier != "none" and buyable
               else "a poor direct fit")
    rationale = (
        f"{name} is {verdict} for Konfyd. As a {industry.lower()} business it "
        f"{'carries merchant credit risk directly' if risk_carrier in ('principal', 'sponsor_bank') else 'absorbs sub-merchant defaults through its sponsor' if risk_carrier == 'sponsored' else 'does not carry settlement risk'}"
        f", and the {signal.replace('_', ' ')} signal means "
        f"{'exposure has just moved' if signal != 'award_recognition' else 'growth is outpacing its underwriting base'}. "
        f"{matched[0]}."
    )
    return rationale, matched, concerns


def _article_url(source: str, slug: str, sig: str) -> str:
    """A link that actually points at the outlet we said we read it in."""
    domain = SOURCE_DOMAINS.get(source, "digitaltransactions.net")
    if domain == "sec.gov":
        return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={slug}"
    return f"https://www.{domain}/{slug}-{sig.replace('_', '-')}"


def _headline(name, sig):
    return {
        "funding": f"{name} raises growth round to scale its merchant acquiring portfolio",
        "expansion": f"{name} extends acquiring licence into new markets",
        "hiring": f"{name} builds out merchant risk and underwriting team",
        "product_launch": f"{name} launches payfac-as-a-service for platform partners",
        "leadership_hire": f"{name} appoints Chief Risk Officer to lead merchant risk",
        "merger_acquisition": f"{name} acquires merchant portfolio in consolidation deal",
        "partnership": f"{name} signs sponsorship deal to expand merchant reach",
        "award_recognition": f"{name} named among fastest-growing payment processors",
    }.get(sig, f"{name} in the news")


def _reason(name, sig):
    return {
        "funding": f"{name} just raised to grow its acquiring book. Growth targets collide with "
                   f"the collateral they post to their sponsor almost immediately — the moment "
                   f"releasing collateral is worth more to them than any new feature.",
        "expansion": f"{name} is entering new markets, which means underwriting merchants under an "
                     f"unfamiliar risk profile and posting fresh scheme collateral in each region. "
                     f"New exposure they have no loss history to price.",
        "hiring": f"{name} is hiring merchant risk and underwriting staff — they are scaling "
                  f"underwriting by headcount, which is exactly the constraint Konfyd removes.",
        "product_launch": f"{name} is launching payfac / embedded payments capability, so they now "
                          f"underwrite sub-merchants at volume. Insolvency prediction moves from "
                          f"nice-to-have to the thing that caps their growth.",
        "leadership_hire": f"{name} brought in a new risk leader. A new CRO's first 90 days are spent "
                           f"re-examining reserve policy and loss provisioning — the single best "
                           f"window to change how tail risk is priced.",
        "merger_acquisition": f"{name} absorbed another portfolio, inheriting merchants it did not "
                              f"underwrite. Unpriced tail risk on an unfamiliar book is the most "
                              f"acute version of the problem Konfyd solves.",
        "partnership": f"{name} signed a distribution or sponsorship deal that will push more "
                       f"merchant volume — and more default exposure — through the same balance sheet.",
        "award_recognition": f"{name} was recognised for growth, a proxy for merchant count climbing "
                             f"faster than its underwriting and capital base.",
    }.get(sig, f"{name} shows a strong buying signal for merchant-risk infrastructure.")


def _tier(score):
    if score >= 75:
        return "A"
    if score >= 55:
        return "B"
    if score >= 35:
        return "C"
    return "D"


def _fill(t: str, person: Person, *, footer: bool = False) -> str:
    first = person.name.split(" ")[0]
    company = person.company.name if person.company else ""
    out = (
        t.replace("{{first_name}}", first)
        .replace("{{name}}", person.name)
        .replace("{{title}}", person.title)
        .replace("{{company}}", company)
    )
    if footer:
        out += EMAIL_FOOTER.replace(
            "{{unsubscribe_url}}",
            f"https://konfyd.com/u/{(person.id or 0):x}",
        )
    return out


def _subject_for(person: Person, fallback: str) -> str:
    """Subject follows the signal that surfaced the account, not the campaign."""
    signal = person.company.signal_type if person.company else ""
    return SUBJECT_BY_SIGNAL.get(signal) or fallback


#: slug -> risk_carrier, so copy can fork on who actually holds the risk.
RISK_CARRIER_BY_SLUG = {s[1]: s[6] for s in COMPANY_SEEDS}


def _variant_for(step, person: Person):
    """Pick the step-1 variant that matches how this company carries risk.

    A principal scheme member is genuinely the guarantor of last resort. A
    sponsored payfac is not — its sponsor holds the paper and sets the collateral
    formula. Sending the principal version to a payfac CRO is factually wrong and
    is exactly the kind of error that ends a conversation, so the fork is applied
    at send time rather than left to the bandit.
    """
    slug = person.company.slug if person.company else ""
    carrier = RISK_CARRIER_BY_SLUG.get(slug, "principal")
    idx = {"principal": 0, "sponsor_bank": 1}.get(carrier, 2)
    return step.variants[min(idx, len(step.variants) - 1)]


# --- email / LinkedIn step definitions ---
#
# Copy rules these follow, because they're what actually works selling into
# payments risk & finance:
#   * Lead with the mechanic (they are the guarantor of last resort), not the product.
#   * Use their vocabulary: deferred delivery, rolling reserves, sponsor collateral,
#     scheme collateral, excessive-dispute programmes, loss provisioning.
#   * Every claim is a number they can argue with — vague "AI-powered" language
#     gets deleted by a CRO in under a second.
#   * Ask for a diagnostic conversation, never a "quick demo".
EMAIL_STEP_DEFS = [
    {
        "order": 1, "name": "Intro",
        "angle": "signal-led: name the event, then the deferred-delivery consequence", "wait": 0,
        # Subject is chosen from the signal that surfaced the account, so a new CRO
        # never gets an email about a funding round that didn't happen.
        "subjects": [
            "Who eats the loss when a {{company}} merchant folds?",
            "Days of deferred delivery on the {{company}} book",
            "{{company}}'s reserve vs. what you actually wrote off",
        ],
        "bodies": [
            # Principal scheme member: they are genuinely the liable party.
            "Hi {{first_name}},\n\nSaw the news at {{company}}. Congratulations — though I'd guess it also means underwriting is now the thing standing between you and your merchant-growth number.\n\nThe exposure that actually hurts isn't last week's dispute rate. It's deferred delivery: the paid-but-undelivered obligations sitting on your book right now. When a travel or ticketing merchant fails, you don't get one month of chargebacks, you get twelve months of forward bookings arriving at once — and as a principal member that lands on you. So you hold reserves and post collateral to cover a loss nobody can size, which locks up balance sheet and costs you the merchants who wouldn't accept the deposit.\n\nKonfyd prices that tail risk instead of collateralising it. We flag insolvency ahead of the event and take the exposure as a rated counterparty, so the hold reflects priced risk rather than worst case.\n\nWorth 20 minutes on one number: how many days of deferred delivery are you carrying on the travel book, and what's the reserve against it? Every acquirer I ask knows the reserve instantly and has to go and find the delivery figure. That gap is the conversation.\n\nBest,\nLeslie Chacko\nCo-Founder, Konfyd",
            # Sponsor bank: residual across a portfolio of sponsored entities, priced
            # with one blanket formula because they can't see the sub-merchant books.
            "Hi {{first_name}},\n\nYou sponsor a book of payfacs and PSPs onto the schemes, and my guess is you price nearly all of them off the same collateral formula — because you can't see into their sub-merchant books. That formula is either too loose on the one that fails or too tight on the twenty that don't, and usually both at once.\n\nKonfyd underwrites sub-merchant insolvency at merchant level across every entity you sponsor and takes the exposure as a rated counterparty. That gives you collateral sized to measured risk per sponsored programme instead of a blanket multiple — and it lets you sponsor the programmes you currently decline.\n\nWorth 20 minutes on one question: across your sponsored portfolio, what's the spread between the collateral you hold and the losses you've actually taken, per entity? Nobody I ask can answer that at entity level.\n\nLeslie Chacko\nCo-Founder, Konfyd",
            # Sponsored entity: their sponsor holds the paper, but the loss flows back.
            "Hi {{first_name}},\n\nQuick question rather than a pitch: when a sub-merchant on the {{company}} book goes under, who ends up wearing it — and who decides the reserve you hold against that happening?\n\nFor most sponsored payfacs the honest answer is that the sponsor bank sets a blanket collateral formula, because they can't see into your sub-merchant book. You carry the economics of a number you didn't set.\n\nKonfyd underwrites that exposure at merchant level and takes it as a rated counterparty — which gives your sponsor something specific to price against instead of a formula, and gives you back the capital and the segments underwriting currently declines.\n\nIf the reserve your sponsor sets is bigger than your actual loss experience, that's worth 20 minutes. And if this sits upstream with them rather than you, tell me and I'll go there instead.\n\nLeslie Chacko\nCo-Founder, Konfyd",
        ],
    },
    {
        "order": 2, "name": "Value nudge",
        "angle": "quantify in bps of TPV — the metric acquirers actually use", "wait": 3,
        "subjects": [
            "The gap between held and realised, in bps",
            "Following up on deferred delivery",
        ],
        "bodies": [
            "Hi {{first_name}},\n\nFollowing up with the number that tends to land.\n\nMost acquirers run somewhere between 1 and 3 bps of TPV in realised merchant credit losses, and hold 5 to 10 bps against it. If {{company}} is anywhere near that range, the difference is capital earning nothing — while underwriting declines travel, events and subscription merchants because the reserve maths never clears.\n\nKonfyd changes the maths rather than the appetite: we take the insolvency exposure at merchant level, so the hold reflects priced risk. Structured as a collateralised facility with rated paper, so your sponsor and your auditor both have something to recognise — that's usually the first question your risk committee asks, and rightly.\n\nHappy to walk through your own held-vs-realised in bps on one call. You keep the analysis either way.\n\nLeslie",
        ],
    },
    {
        "order": 3, "name": "Short bump",
        "angle": "one sharp diagnostic question, very short", "wait": 4,
        "subjects": ["One question, {{first_name}}"],
        "bodies": [
            "Hi {{first_name}},\n\nOne question and I'll leave it there: at onboarding, does {{company}} price a merchant's insolvency risk, or size a reserve against it?\n\nIf it's the second, there's a conversation worth having. If merchant credit risk isn't yours to own, just point me at whoever sets the reserve and I'll stop bothering you.\n\nLeslie",
        ],
    },
    {
        "order": 4, "name": "Breakup",
        "angle": "polite break-up, leave the trigger behind", "wait": 5,
        "subjects": ["Closing the loop"],
        "bodies": [
            "Hi {{first_name}},\n\nI'll stop here — clearly not the moment.\n\nOne thing worth keeping: the trigger for most processors isn't a good quarter, it's a bad merchant. When something with a forward-booking book fails and twelve months of deferred delivery arrives as disputes, reserve policy gets rewritten inside a month. The teams that handle it well already knew their deferred-delivery number.\n\nIf that happens at {{company}}, or the capital behind reserves becomes someone's target, I'm easy to find.\n\nAll the best,\nLeslie Chacko\nCo-Founder, Konfyd",
        ],
    },
]

# CAN-SPAM requires a physical postal address and a working opt-out in every
# commercial email; PECR/GDPR require the same for the UK/EU half of this list.
# The footer is appended to every rendered body, not left to the copywriter.
EMAIL_FOOTER = (
    "\n\n—\nKonfyd, 78 SW 7th Street, Miami, FL 33130, USA\n"
    "Not relevant? {{unsubscribe_url}} and I won't contact you again."
)

LINKEDIN_STEP_DEFS = [
    {"order": 1, "name": "Connection request", "kind": "invite",
     "angle": "signal-led, peer-to-peer, no pitch, ≤300 chars", "wait": 0,
     "template": "Hi {{first_name}} — saw the {{company}} news. I work on merchant insolvency risk and capital release for acquirers, so I pay attention to how teams handle reserve policy through a growth phase. Would be good to connect."},
    {"order": 2, "name": "Intro message", "kind": "message",
     "angle": "thanks + one soft diagnostic question", "wait": 0,
     "template": "Thanks for connecting, {{first_name}}. Genuinely curious rather than pitching: as {{company}} scales the book, do you track days of deferred delivery alongside dispute rate? Most risk teams know their reserve number cold and have to go looking for the delivery number — which is the one that decides how bad an insolvency actually gets."},
    {"order": 3, "name": "Value nudge", "kind": "message",
     "angle": "one concrete number in bps, low-friction ask", "wait": 3,
     "template": "One data point in case it's useful — acquirers typically realise 1-3 bps of TPV in merchant credit losses and hold 5-10 bps against it. We underwrite that exposure at merchant level and take it as a rated counterparty, so the hold reflects priced risk and the capital comes back. Worth 20 minutes on your own held-vs-realised?"},
    {"order": 4, "name": "Breakup", "kind": "message",
     "angle": "polite last touch, easy to say no", "wait": 4,
     "template": "No problem if the timing's off, {{first_name}} — I'll leave it there. If a merchant with a forward-booking book ever fails on you, or the capital behind reserves becomes a target, happy to pick it up then."},
]

# Subject line follows the signal that surfaced the account — one sequence serves
# four campaigns, so a hardcoded "after the raise" would be wrong three times out
# of four.
SUBJECT_BY_SIGNAL = {
    "funding": "{{company}}'s reserves after the raise",
    "leadership_hire": "Your first 90 days on reserve policy",
    "merger_acquisition": "The book you just inherited",
    "expansion": "New market, no loss history",
    "product_launch": "Underwriting sub-merchants at {{company}}",
    "hiring": "Scaling underwriting by headcount",
    "partnership": "More volume, same balance sheet",
    "award_recognition": "Who eats the loss when a {{company}} merchant folds?",
}

THEME_FOR_SIGNAL = {
    "funding": "post-raise-capital",
    "product_launch": "payfac-underwriting",
    "hiring": "payfac-underwriting",
    "leadership_hire": "new-cro",
    "merger_acquisition": "portfolio-ma",
    "expansion": "portfolio-ma",
    "partnership": "post-raise-capital",
    "award_recognition": "post-raise-capital",
}

CAMPAIGN_DEFS = [
    {"name": "Growth Capital — Risk & Finance Leaders",
     "desc": "Processors and PSPs that just raised. Targets CROs and CFOs while growth "
             "targets are colliding with reserve and sponsor-collateral requirements.",
     "status": "active", "min": 55, "theme": "post-raise-capital", "age": 48},
    {"name": "Payfac Launch — Underwriting Owners",
     "desc": "Platforms launching payfac-as-a-service or embedded payments, who now "
             "underwrite sub-merchants at volume. Targets Heads of Underwriting and Risk.",
     "status": "active", "min": 50, "theme": "payfac-underwriting", "age": 35},
    {"name": "New CRO — First 90 Days",
     "desc": "Newly appointed Chief Risk Officers and risk leaders, caught while reserve "
             "policy and loss provisioning are actively under review.",
     "status": "active", "min": 45, "theme": "new-cro", "age": 22},
    {"name": "Sponsor Residual — Collateral Formula Owners",
     "desc": "BIN-sponsoring banks that carry residual on every payfac they sponsor and "
             "price it with one blanket formula. Targets Chief Credit Officers and Heads "
             "of Merchant Sponsorship. One relationship unlocks a portfolio.",
     "status": "active", "min": 70, "theme": "sponsor-residual", "age": 30},
    {"name": "Portfolio M&A — Inherited Risk",
     "desc": "Acquirers that just absorbed a merchant portfolio they did not underwrite. "
             "Highest-urgency segment: unpriced tail risk on an unfamiliar book.",
     "status": "paused", "min": 60, "theme": "portfolio-ma", "age": 12},
]


def _build_email_steps(seq: Sequence) -> list[SequenceStep]:
    variant_names = ["Principal", "Sponsor bank", "Sponsored"]
    angles = ["guarantor-of-last-resort framing for principal members",
              "blanket-collateral-formula framing for sponsor banks",
              "sponsor-sets-your-reserve framing for sponsored payfacs"]
    steps = []
    for si, d in enumerate(EMAIL_STEP_DEFS):
        step = SequenceStep(sequence=seq, step_order=d["order"], name=d["name"], angle=d["angle"], wait_days=d["wait"], kind=None)
        n_variants = 3 if si == 0 else (2 if si == 1 else 1)
        for vi in range(n_variants):
            sent = randint(40, 320)
            reply = round(sent * (0.02 + rand() * 0.12))
            step.variants.append(Variant(
                name=variant_names[vi], angle=angles[vi],
                subject_template=d["subjects"][vi % len(d["subjects"])],
                body_template=d["bodies"][vi % len(d["bodies"])],
                sent_count=sent, reply_count=reply, alpha=1 + reply, beta=1 + (sent - reply),
                is_winner=(vi == 0 and si == 0), is_paused=False,
            ))
        steps.append(step)
    return steps


def _build_linkedin_steps(seq: Sequence) -> list[SequenceStep]:
    variant_names = ["Warm", "Direct"]
    steps = []
    for si, d in enumerate(LINKEDIN_STEP_DEFS):
        step = SequenceStep(sequence=seq, step_order=d["order"], name=d["name"], angle=d["angle"], wait_days=d["wait"], kind=d["kind"])
        n_variants = 2 if si == 0 else 1
        for vi in range(n_variants):
            sent = randint(30, 180)
            reply = round(sent * (0.05 + rand() * 0.15))
            step.variants.append(Variant(
                name=variant_names[vi], angle=("warm, relationship-first" if vi == 0 else "direct, value-first"),
                subject_template=None, body_template=d["template"],
                sent_count=sent, reply_count=reply, alpha=1 + reply, beta=1 + (sent - reply),
                is_winner=(vi == 0 and si == 0), is_paused=False,
            ))
        steps.append(step)
    return steps


def _reply_body(rc: str, person: Person) -> str:
    """Replies vary by contact so the inbox doesn't read like one person wrote it.

    Insolvency terminology follows the contact's jurisdiction: a US merchant files
    Chapter 11, a UK/EU one goes into administration. Getting that backwards is
    the kind of detail a payments operator notices immediately.
    """
    first = person.name.split(" ")[0]
    company = person.company.name if person.company else "our book"
    loc = (person.company.location if person.company else "") or ""
    country = loc.split(",")[-1].strip() if "," in loc else ""
    # Insolvency is a jurisdictional term of art; guessing wrong is an instant tell.
    insolvency = {
        "UK": "went into administration", "EU": "went into administration",
        "US": "filed Chapter 11", "CA": "filed under the CCAA",
        "BR": "entered recuperação judicial", "UY": "entered concurso",
        "SG": "entered judicial management", "AU": "went into voluntary administration",
        "IN": "entered insolvency under the IBC",
    }.get(country, "went insolvent")
    failure = "an airline consolidator" if country in ("UK", "EU") else "a ticketing platform"

    variants = {
        "interested": [
            f"Your timing is annoyingly good. We took a seven-figure hit when {failure} "
            f"{insolvency} last year and the board has been asking about reserve adequacy "
            f"ever since. Send some times next week — I'd want our treasury lead on it too. — {first}",
            f"This is relevant. We're carrying more deferred delivery than I'd like on the events "
            f"book and our current answer is just a bigger rolling reserve, which the commercial "
            f"team hates. Worth a conversation — what do you need from us to size it? — {first}",
            f"Happy to talk. Fair warning: the question that will decide this is whether our "
            f"auditors let us release the provision, or whether this just sits on top of an "
            f"unchanged reserve. If you have a clean answer on accounting treatment, book time. — {first}",
            f"Interested, with a caveat — we've looked at chargeback insurance twice and both times "
            f"the pricing assumed a loss rate nothing like ours. If you're underwriting at merchant "
            f"level rather than portfolio level, that's different. Send times. — {first}",
        ],
        "objection": [
            "We already hold reserves sized off our own loss history, and our sponsor bank has a "
            "collateral formula we can't unilaterally change. What does your model see at "
            "onboarding that our underwriting team doesn't?",
            "Two things before we spend time on this: is your paper rated, and will a sponsor bank "
            "actually recognise it for capital relief? Unrated counterparty means no relief, in "
            "which case we've just bought insurance and changed nothing.",
            f"We looked at this category last year. The blocker wasn't the model, it was that "
            f"writing financial guarantees is monoline-restricted in a couple of the states we "
            f"operate in. How are you structured around that?",
            "Honestly? Our realised merchant losses last year were under 2 bps. Convince me the "
            "capital we'd release is worth more than what you'd charge to take a risk that "
            "mostly doesn't materialise.",
        ],
        "referral": [
            f"Merchant credit risk sits with our CRO rather than me — I'll introduce you. Lead with "
            f"the held-versus-realised comparison in bps, that's the number he argues about. — {first}",
            f"Wrong person, but useful: our Treasurer owns the collateral we post to our sponsor, so "
            f"the capital-release argument is hers. Copying her in. — {first}",
            f"This is a credit committee question at {company}, not mine. I'll flag it to our Chief "
            f"Credit Officer — he's rebuilding the provisioning model this quarter anyway. — {first}",
        ],
        "not_interested": [
            "We're mid-migration on our onboarding stack and not looking at anything new until "
            "that's done. Try me next year.",
            "Our sponsor sets the reserve and we have no room to renegotiate it mid-term. Not a "
            "no forever, but there's nothing I can action.",
            "We self-insure merchant losses and the treasury team is comfortable with the current "
            "hold. Appreciate the note though.",
        ],
    }
    pool = variants.get(rc)
    if not pool:
        return "Got it, thanks."
    # Stable per person, so the same contact always says the same thing.
    return pool[(person.id or len(person.name)) % len(pool)]


EMAIL_STATUS_POOL = (
    ["active"] * 16 + ["completed"] * 9 + ["not_interested"] * 7 + ["bounced"] * 3
    + ["replied"] * 3 + ["in_conversation"] + ["needs_human"] + ["meeting"] + ["booked"]
)
LI_STATUS_POOL = (
    ["pending"] * 4 + ["invite_sent"] * 9 + ["accepted"] * 6 + ["invite_expired"] * 5
    + ["completed"] * 6 + ["not_interested"] * 4 + ["in_conversation"] * 2 + ["meeting"] + ["booked"]
)


# --------------------------------------------------------------------------- #
# Deals (Closer stage) — hand-authored so the demo reads like a real pipeline.
#
# These stand in for what the Closer module will produce from meeting
# transcripts once it ships: a per-meeting summary, the extracted takeaways /
# objections / questions / commitments, an AI read on what could kill the deal,
# and the ranked next steps to actually close it.
# --------------------------------------------------------------------------- #

DEAL_SEEDS: tuple[dict, ...] = (
    {
        "company": "nuvei",
        "person": {
            "name": "Priya Raghavan", "title": "SVP & Chief Risk Officer", "role": "Chief Risk Officer",
            "email": "priya.raghavan@nuvei.com", "city": "Montreal", "country": "CA",
        },
        "deal": {
            "stage": "proposal", "health": "on_track", "probability": 65, "value_usd": 1850000,
            "expected_close": "2026-08-29", "source_channel": "email", "opened_days": 24,
            "summary": (
                "Strong champion in Priya, and a quantified problem: they hold $94M against "
                "merchant default and wrote off $16M last year. On ~$200B TPV that is 4.7 bps held "
                "against 0.8 bps realised — a 5.9x gap "
                "the board has already flagged. The gate is credit committee and their sponsor "
                "bank's view on whether our paper qualifies for capital relief, not price. Proposal for a $40M "
                "first-tranche facility on the high-risk travel and ticketing book is with "
                "Priya; she needs Daniel (CFO) to co-sign, and he joins the next call."
            ),
        },
        "meetings": (
            {
                "title": "Intro call — reserve adequacy", "kind": "discovery", "days_ago": 24,
                "duration": 30, "sentiment": "positive",
                "attendees": "Priya Raghavan, Leslie Chacko",
                "summary": (
                    "Priya walked through their reserve methodology: sized off three years of "
                    "internal loss history, applied per-MCC, with rolling deposits on anything "
                    "in travel or events. Holding roughly $94M in reserves and posted "
                    "collateral against $16M of realised merchant-default losses last year — 4.7 bps "
                    "against 0.8 bps on their volume. "
                    "She raised that gap with the board herself two quarters ago, so this is "
                    "her agenda rather than ours. Underwriting currently declines most travel "
                    "and ticketing volume because the reserve maths never clears."
                ),
                "takeaways": (
                    "4.7 bps of TPV held against 0.8 bps realised ($94M vs $16M on ~$200B) — a board topic",
                    "Underwriting declines most travel/ticketing on reserve maths alone",
                    "Priya owns reserve policy; CFO co-signs anything balance-sheet affecting",
                    "Rolling deposits are costing them merchants at renewal",
                ),
                "objections": (
                    "Sponsor bank sets their collateral formula and won't move it for an unrated counterparty",
                    "Auditors may treat this as insurance sitting on top of an unchanged provision — "
                    "in which case the reserve never actually comes down",
                ),
                "questions": (
                    "How far ahead of an insolvency event does the model actually fire?",
                    "Who holds the exposure legally once you assume it — and rated by whom?",
                    "Will our auditors let us release the provision, or does it sit on top of it?",
                ),
                "commitments": (
                    "Leslie to send the insolvency-prediction lead-time study and counterparty structure",
                    "Priya to pull the declined-volume report for travel and ticketing",
                ),
            },
            {
                "title": "Model validation with risk analytics", "kind": "technical", "days_ago": 13,
                "duration": 45, "sentiment": "positive",
                "attendees": "Priya Raghavan, Marcus Okonkwo, Elena Lindqvist, Leslie Chacko",
                "summary": (
                    "Back-tested against 18 months of their own defaults. The model flagged 71% "
                    "KS 0.58 against their own 18-month default population, with 64% of defaults in the "
                    "top decile — including two of the three largest write-offs their internal "
                    "scorecard had rated acceptable throughout. Marcus pushed hard on the swap-set: "
                    "at their own decline rate, which merchants would we have declined that they "
                    "approved, and which did they decline that we would have taken. We showed 4 of "
                    "their 5 largest write-offs on the decline side. Elena raised "
                    "that settlement data would need to leave their environment; we walked "
                    "through the aggregation boundary and it landed."
                ),
                "takeaways": (
                    "KS 0.58 on their own 18-month default population; 64% of defaults in the top decile",
                    "Caught two of their three largest write-offs that internal scoring missed",
                    "Swap-set: would have declined 4 of their 5 largest write-offs while approving 11% more",
                    "They want to start on travel/ticketing only, then extend to subscriptions",
                ),
                "objections": (
                    "Settlement data leaving their environment needs InfoSec sign-off",
                    "Marcus wants the swap-set re-run at their exact decline rate, not ours",
                ),
                "questions": (
                    "Can the threshold be tuned per MCC rather than portfolio-wide?",
                    "What happens to the facility if loss rates exceed the priced assumption?",
                ),
                "commitments": (
                    "Leslie to provide per-MCC threshold config and the InfoSec pack",
                    "Marcus to re-run the swap-set at their own decline rate",
                ),
            },
            {
                "title": "Facility structure and pricing", "kind": "pricing", "days_ago": 5,
                "duration": 30, "sentiment": "positive",
                "attendees": "Priya Raghavan, Leslie Chacko",
                "summary": (
                    "Landed on a $40M first-tranche facility covering the travel and ticketing "
                    "book, priced on the back-tested loss curve with a quarterly reset. Priya "
                    "asked for a 12-month step-down on the fee if realised losses come in under "
                    "the priced assumption — the one open commercial term. She takes it to "
                    "credit committee on the 14th; Daniel needs to be comfortable first."
                ),
                "takeaways": (
                    "$40M first tranche on travel + ticketing, quarterly repricing",
                    "Credit committee on the 14th is the real decision point",
                    "InfoSec review is the only remaining technical gate",
                ),
                "objections": (
                    "Wants a fee step-down if realised losses beat the priced curve",
                ),
                "questions": ("Can the facility scale mid-quarter if they onboard a large merchant?",),
                "commitments": (
                    "Leslie to reprice with the step-down and send the credit-committee pack",
                    "Priya to confirm the InfoSec outcome before the 14th",
                ),
            },
        ),
        "upcoming": {
            "title": "Credit committee pre-read with CFO", "kind": "exec", "days_ahead": 4,
            "duration": 30, "attendees": "Priya Raghavan, Daniel Whelan, Leslie Chacko",
        },
        "next_steps": (
            {
                "title": "Get written accounting-treatment confirmation before committee",
                "detail": "This is the real deal-killer and nobody has answered it. Get their audit "
                          "partner on a call with our structuring counsel and secure a written view "
                          "that the protection permits provision release under their framework. If it "
                          "only sits on top of the provision, there is no capital release and no deal — "
                          "better to know now than at committee.",
                "owner": "Leslie Chacko", "due": "2026-08-05", "priority": "high", "status": "todo",
                "rationale": "Raised as a question on the intro call and never closed. Every deal in "
                             "this category dies here or clears here.",
            },
            {
                "title": "Confirm the sponsor bank recognises our paper for capital relief",
                "detail": "Their sponsor grants relief only against a rated counterparty. Get our "
                          "structure and rating in front of the sponsor's credit team directly rather "
                          "than relaying through Priya — unrated means zero relief, which turns the "
                          "capital-release case into an insurance purchase.",
                "owner": "Leslie Chacko", "due": "2026-08-06", "priority": "high", "status": "todo",
                "rationale": "Named explicitly as the sponsor's condition on the intro call.",
            },
            {
                "title": "Reprice with the 12-month fee step-down",
                "detail": "Priya needs the step-down to defend the facility against 'we could just "
                          "self-insure' at committee. Price it into the curve and show both options "
                          "side by side so the committee sees the trade rather than one number.",
                "owner": "Leslie Chacko", "due": "2026-07-29", "priority": "high", "status": "todo",
                "rationale": "Only open commercial term — raised directly in the pricing call on Jul 17.",
            },
            {
                "title": "Get InfoSec review unblocked",
                "detail": "Elena's team opened the review on Jul 13 and it hasn't moved. Offer to join "
                          "their security office hours rather than waiting on questionnaire round-trips — "
                          "this is the only gate that can slip the committee date.",
                "owner": "Leslie Chacko", "due": "2026-07-31", "priority": "high", "status": "todo",
                "rationale": "Named as the last technical gate; committee is on the 14th.",
            },
            {
                "title": "Get Daniel (CFO) fully bought in before committee",
                "detail": "He co-signs anything balance-sheet affecting but has not been in a session. "
                          "Walk him through the capital-release maths and the counterparty structure — "
                          "CFOs kill these on counterparty quality, not on price.",
                "owner": "Leslie Chacko", "due": "2026-08-03", "priority": "high", "status": "todo",
                "rationale": "Economic co-signer with zero direct exposure to the case so far.",
            },
            {
                "title": "Send per-MCC threshold config and InfoSec pack",
                "detail": "Marcus wants thresholds tunable per MCC rather than portfolio-wide.",
                "owner": "Leslie Chacko", "due": "2026-07-20", "priority": "medium", "status": "done",
                "rationale": "Committed on the model validation call.",
            },
            {
                "title": "Re-run the swap-set at their own decline rate",
                "detail": "Marcus is re-running this himself. Get ahead of it: the swap-set at their exact "
                          "decline rate, showing which merchants we would have declined that they approved, "
                          "and which they declined that we would have taken. Reconcile before committee, "
                          "not during it.",
                "owner": "Marcus Okonkwo", "due": "2026-08-07", "priority": "medium", "status": "todo",
                "rationale": "Swap-set is the artefact every risk committee demands before adopting a scorecard — "
                             "and it is the one analysis being run outside our control.",
            },
        ),
        "highlights": (
            ("blocker", "Accounting treatment unresolved: if auditors won't let them release the "
                        "provision, the reserve never comes down and the whole case collapses", 0.89),
            ("blocker", "Sponsor bank grants capital relief only against rated paper — our "
                        "counterparty structure has to clear their credit team, not just Priya's", 0.86),
            ("strength", "5.9x held-vs-realised gap (4.7 vs 0.8 bps) the champion raised with the board", 0.93),
            ("strength", "Back-test caught two of their three largest write-offs their scorecard missed", 0.91),
            ("strength", "Declined travel/ticketing volume gives a clean revenue case, not just a cost case", 0.86),
            ("risk", "CFO co-signs but has not attended a single session", 0.72),
            ("risk", "Sponsor bank's capital-relief treatment of our paper is outside their control", 0.68),
            ("blocker", "InfoSec review opened Jul 13 and has not progressed; committee is Aug 14", 0.81),
            ("signal", "Asked whether the facility can scale mid-quarter — planning for growth, not evaluating", 0.74),
        ),
    },
    {
        "company": "finix",
        "person": {
            "name": "Marcus Baptiste", "title": "VP Merchant Risk & Underwriting", "role": "VP Underwriting",
            "email": "marcus.baptiste@finix.com", "city": "San Francisco", "country": "US",
        },
        "deal": {
            "stage": "negotiation", "health": "on_track", "probability": 80, "value_usd": 2400000,
            "expected_close": "2026-08-14", "source_channel": "linkedin", "opened_days": 41,
            "summary": (
                "Furthest-along deal in the book, and the cleanest fit: as a payfac-as-a-service "
                "platform they underwrite sub-merchants at volume, and sub-merchant insolvency "
                "is their single largest loss line. Marcus ran a 4-week shadow evaluation and "
                "has internal numbers — the model surfaced 3.1x more true insolvency risk than "
                "their onboarding scorecard at equivalent decline rates. Legal is redlining "
                "loss-allocation language and procurement wants multi-year pricing. The real "
                "risk is build-vs-buy: Marcus has mentioned an internal scoring project twice."
            ),
        },
        "meetings": (
            {
                "title": "Intro — sub-merchant default exposure", "kind": "discovery", "days_ago": 41,
                "duration": 30, "sentiment": "positive",
                "attendees": "Marcus Baptiste, Leslie Chacko",
                "summary": (
                    "Marcus arrived already convinced of the problem — he'd circulated an internal "
                    "memo on sub-merchant default concentration the month before. Their platform "
                    "partners onboard SMBs fast, and Finix carries the residual. He wanted expert "
                    "detail on model performance rather than any explanation of the pain."
                ),
                "takeaways": (
                    "Marcus had already written the internal memo — no problem education needed",
                    "Sub-merchant default is their largest single loss line",
                    "Platform partners want faster onboarding; risk wants slower — classic tension",
                ),
                "objections": ("Sceptical that an external model beats their own onboarding data",),
                "questions": ("What's the lift versus our scorecard at the same decline rate?",),
                "commitments": ("Leslie to set up a 4-week shadow evaluation on live onboarding traffic",),
            },
            {
                "title": "Shadow evaluation kickoff", "kind": "technical", "days_ago": 33,
                "duration": 45, "sentiment": "positive",
                "attendees": "Marcus Baptiste, Sofia Ferreira, Leslie Chacko",
                "summary": (
                    "Wired scoring into a mirrored stream of onboarding decisions with no effect on "
                    "live approvals. Sofia built the integration in an afternoon. Agreed to measure "
                    "true insolvency capture against their scorecard at matched decline rates over "
                    "four weeks."
                ),
                "takeaways": (
                    "Shadow integration built in one afternoon",
                    "Measuring insolvency capture at matched decline rates — their metric, not ours",
                    "Zero impact on live approvals during evaluation",
                ),
                "objections": (),
                "questions": ("Can we export the raw scoring data for our own analysis?",),
                "commitments": ("Sofia to share a weekly readout",),
            },
            {
                "title": "Evaluation results review", "kind": "exec", "days_ago": 14,
                "duration": 45, "sentiment": "positive",
                "attendees": "Marcus Baptiste, Sofia Ferreira, Rachel Mbeki, Leslie Chacko",
                "summary": (
                    "The numbers carried the room: at matched decline rates the model surfaced 3.1x "
                    "more genuine insolvency risk than their scorecard, and flagged four sub-merchants "
                    "that subsequently defaulted and their scorecard had approved. Rachel (CFO) went "
                    "straight to build-vs-buy. Marcus's answer was that the hard part is the loss data "
                    "across acquirers, not the model — correct, and in our favour, but he framed it as "
                    "an open question rather than a settled one."
                ),
                "takeaways": (
                    "3.1x more insolvency risk surfaced at matched decline rates over 4 weeks",
                    "Flagged four sub-merchants that later defaulted after scorecard approval",
                    "CFO now engaged and asking commercial rather than technical questions",
                ),
                "objections": ("Rachel raised build-vs-buy: 'the modelling doesn't look that hard'",),
                "questions": (
                    "What does pricing look like at 5x this onboarding volume?",
                    "Can we get a multi-year rate lock?",
                ),
                "commitments": (
                    "Leslie to send volume-tiered pricing including a 2-year option",
                    "Marcus to start legal review",
                ),
            },
            {
                "title": "Commercial terms — round 1", "kind": "pricing", "days_ago": 4,
                "duration": 30, "sentiment": "neutral",
                "attendees": "Marcus Baptiste, Rachel Mbeki, Leslie Chacko",
                "summary": (
                    "Procurement-led. Rachel pushed for two years at 22% off list; we countered at 15% "
                    "with a volume ratchet. Legal has three redlines, all on how losses are allocated "
                    "when the model flags a merchant and Finix approves anyway. Marcus mentioned in "
                    "passing that an analyst had 'started building something similar internally' — the "
                    "second time build-vs-buy has come up."
                ),
                "takeaways": (
                    "Rachel wants 2 years at 22% off; we're at 15% plus a volume ratchet",
                    "All three legal redlines are the same issue: loss allocation on override",
                    "An internal scoring prototype exists — build-vs-buy is live again",
                ),
                "objections": (
                    "22% vs 15% discount gap on the multi-year commitment",
                    "Loss allocation when Finix overrides a model flag is unacceptable as drafted",
                ),
                "questions": ("Would you do 20% with quarterly-in-advance settlement?",),
                "commitments": (
                    "Leslie to get legal's position on override loss allocation by Wednesday",
                    "Rachel to send the redlined agreement",
                ),
            },
        ),
        "upcoming": {
            "title": "Legal redline working session", "kind": "technical", "days_ahead": 2,
            "duration": 45, "attendees": "Marcus Baptiste, Rachel Mbeki, Leslie Chacko",
        },
        "next_steps": (
            {
                "title": "Close the override loss-allocation redline",
                "detail": "All three redlines reduce to one question: who wears the loss when we flag a "
                          "merchant and Finix approves anyway. Propose the standard split — our exposure "
                          "caps at the priced assumption, overrides sit with them — which has cleared at "
                          "two comparable payfacs.",
                "owner": "Leslie Chacko", "due": "2026-07-29", "priority": "high", "status": "todo",
                "rationale": "Only contractual blocker; we committed to a Wednesday answer.",
            },
            {
                "title": "Kill build-vs-buy with the cross-acquirer data argument",
                "detail": "Raised twice, and a prototype now exists. Send the data-network breakdown: the "
                          "model works because it sees defaults across many acquirers' books. Finix sees "
                          "only its own. The modelling is a quarter; the data is years.",
                "owner": "Leslie Chacko", "due": "2026-07-30", "priority": "high", "status": "todo",
                "rationale": "Mentioned on both of the last two calls and trending, not fading.",
            },
            {
                "title": "Land the discount at 20% with quarterly-in-advance",
                "detail": "Rachel floated the shape herself. Take it — the settlement timing is worth the "
                          "five points and it closes the last commercial gap while making her the author "
                          "of the deal rather than its opponent.",
                "owner": "Leslie Chacko", "due": "2026-08-04", "priority": "high", "status": "todo",
                "rationale": "Accepting a buyer's own proposal is the cheapest way to convert them.",
            },
            {
                "title": "Send volume-tiered pricing with 2-year option",
                "detail": "Tiers at current, 2x and 5x onboarding volume with the multi-year rate lock.",
                "owner": "Leslie Chacko", "due": "2026-07-15", "priority": "medium", "status": "done",
                "rationale": "Committed at the evaluation results review.",
            },
            {
                "title": "Turn the evaluation results into a one-pager Rachel can circulate",
                "detail": "3.1x insolvency capture and the four missed defaults, framed against their own "
                          "scorecard. She needs something she can forward to her board without us in the room.",
                "owner": "Leslie Chacko", "due": "2026-08-05", "priority": "medium", "status": "todo",
                "rationale": "Economic buyer needs ammunition that survives our absence.",
            },
        ),
        "highlights": (
            ("strength", "Evaluation produced their own number: 3.1x insolvency capture at matched declines", 0.95),
            ("strength", "Four sub-merchants flagged then defaulted after their scorecard approved them", 0.93),
            ("strength", "Champion wrote the internal problem memo before we engaged", 0.89),
            ("strength", "CFO is negotiating terms rather than evaluating fit", 0.83),
            ("risk", "Build-vs-buy raised twice; an internal scoring prototype now exists", 0.78),
            ("risk", "22% vs 15% discount gap still open with procurement", 0.55),
            ("blocker", "Loss allocation on model override is unacceptable as drafted", 0.74),
            ("signal", "Asked for a multi-year rate lock — negotiating shape, not deciding whether", 0.87),
        ),
    },
    {
        "company": "tilled",
        "person": {
            "name": "Daniel Whelan", "title": "Chief Financial Officer", "role": "Chief Financial Officer",
            "email": "daniel.whelan@tilled.com", "city": "Boulder", "country": "US",
        },
        "deal": {
            "stage": "evaluation", "health": "at_risk", "probability": 35, "value_usd": 320000,
            "expected_close": "2026-09-18", "source_channel": "email", "opened_days": 19,
            "summary": (
                "Real interest, no urgency, and no identified budget owner. Daniel likes the "
                "capital-release argument intellectually but has twice framed this as a 'next "
                "funding cycle' decision. Their sub-merchant losses are genuine but small in "
                "absolute terms, so nobody is bleeding. Worse, their sponsor bank sets the "
                "reserve requirement, and it isn't clear Tilled can change it unilaterally — "
                "which may make this the wrong entity to sell to entirely."
            ),
        },
        "meetings": (
            {
                "title": "Intro call", "kind": "discovery", "days_ago": 19,
                "duration": 30, "sentiment": "positive",
                "attendees": "Daniel Whelan, Leslie Chacko",
                "summary": (
                    "Daniel described sub-merchant defaults running a few hundred thousand a year — "
                    "real, tracked, but not board-level. He was genuinely engaged on the capital-release "
                    "framing and asked for a demo unprompted, then immediately framed any purchase as "
                    "a next-funding-cycle item. Also mentioned their sponsor bank sets the reserve "
                    "requirement, which he isn't sure they can move."
                ),
                "takeaways": (
                    "Sub-merchant defaults in the low hundreds of thousands — real but not urgent",
                    "Daniel engaged on capital release, asked for a demo unprompted",
                    "Purchase framed as next funding cycle",
                    "Sponsor bank sets the reserve requirement — may not be Tilled's decision",
                ),
                "objections": ("No allocated budget this cycle",),
                "questions": ("Does this work if our sponsor bank owns the reserve requirement?",),
                "commitments": ("Leslie to run a session with their risk lead",),
            },
            {
                "title": "Model walkthrough with risk", "kind": "demo", "days_ago": 9,
                "duration": 45, "sentiment": "neutral",
                "attendees": "Daniel Whelan, Nadia Kowalski, Leslie Chacko",
                "summary": (
                    "Technically well received; Nadia was more sceptical than Daniel and pointed out "
                    "they could tighten onboarding criteria for free and accept slower growth. Hard "
                    "to counter at their loss scale. Nobody in the room owns a budget line and Daniel "
                    "could not name who does. The meeting ended with no next step until we proposed one."
                ),
                "takeaways": (
                    "Nadia's alternative — tighter onboarding criteria — is free and credible at their scale",
                    "Nobody in the room owns a budget line; Daniel can't name who does",
                    "They proposed no next step",
                ),
                "objections": (
                    "'We could just tighten onboarding and grow slower'",
                    "Budget framed as next funding cycle again",
                ),
                "questions": ("What's the smallest possible starting facility?",),
                "commitments": ("Leslie to send a minimum-facility option",),
            },
        ),
        "next_steps": (
            {
                "title": "Establish whether Tilled can change its own reserve requirement",
                "detail": "Pathward sponsors Tilled, so if Pathward sets the collateral formula we are "
                          "selling to the wrong entity. Pathward is already an A-tier account in this "
                          "workspace and also sponsors Nexio — one conversation there moves the formula "
                          "for both and answers this question upstream. Qualify it before spending "
                          "another cycle here.",
                "owner": "Leslie Chacko", "due": "2026-07-30", "priority": "high", "status": "todo",
                "rationale": "Raised by Daniel himself on the first call and never resolved. "
                             "Could disqualify the whole opportunity — or redirect it somewhere better.",
            },
            {
                "title": "Find the actual budget owner",
                "detail": "Two meetings and nobody can name who signs. Ask Daniel directly who approved "
                          "their last vendor commitment over $100k and work back from that name.",
                "owner": "Leslie Chacko", "due": "2026-08-01", "priority": "high", "status": "todo",
                "rationale": "No identified economic buyer is the largest single risk here.",
            },
            {
                "title": "Counter tighter-onboarding with the growth cost",
                "detail": "Nadia's alternative is only free if declined merchants are worthless. Build the "
                          "comparison: volume they'd forgo tightening criteria versus the facility cost. "
                          "Send it to Nadia directly rather than through Daniel.",
                "owner": "Leslie Chacko", "due": "2026-08-04", "priority": "medium", "status": "todo",
                "rationale": "Unanswered objection from the more sceptical attendee.",
            },
            {
                "title": "Send the minimum-facility option",
                "detail": "Smallest credible entry point so this can be approved operationally rather than "
                          "waiting on a funding cycle.",
                "owner": "Leslie Chacko", "due": "2026-07-28", "priority": "medium", "status": "todo",
                "rationale": "Daniel asked for it unprompted — the one buying signal from the demo.",
            },
        ),
        "highlights": (
            ("strength", "CFO engaged on capital release and asked for the starter facility himself", 0.71),
            ("risk", "Sponsor bank may own the reserve decision — possibly the wrong entity to sell to", 0.87),
            ("risk", "No economic buyer identified after two meetings", 0.85),
            ("risk", "Loss scale too small to create urgency; timing pushed twice", 0.8),
            ("blocker", "Free alternative — tighter onboarding criteria — went unanswered", 0.69),
        ),
    },
    {
        "company": "paysafe",
        "person": {
            "name": "Gerald Brennan", "title": "Group Chief Risk Officer", "role": "Chief Risk Officer",
            "email": "gerald.brennan@paysafe.com", "city": "London", "country": "UK",
        },
        "deal": {
            "stage": "closed_lost", "health": "stalled", "probability": 0, "value_usd": 1400000,
            "expected_close": "2026-06-30", "source_channel": "email", "opened_days": 132,
            "summary": (
                "Lost, and worth reading before every new deal. We got all the way to credit "
                "committee on a £30M facility over the travel book — champion bought in, model "
                "validated, pricing agreed. Their auditors then ruled that as structured the "
                "cover did not qualify as a transfer of the risks and rewards under IFRS 9, so "
                "the provision had to stay on balance sheet. Insurance on top of an unchanged "
                "reserve releases no capital, and the entire business case was capital release. "
                "Gerald was blunt about it: 'the modelling was never the question.' We spent four "
                "meetings on model performance and raised accounting treatment in the fifth."
            ),
        },
        "meetings": (
            {
                "title": "Post-mortem with Gerald", "kind": "exec", "days_ago": 26,
                "duration": 30, "sentiment": "negative",
                "attendees": "Gerald Brennan, Leslie Chacko",
                "summary": (
                    "Gerald took the call as a favour and was straightforwardly useful. Their "
                    "technical accounting team had concluded the structure left Paysafe exposed to "
                    "enough residual variability that derecognition failed — so the provision "
                    "stayed and the capital never came back. He said any processor of their size "
                    "will reach the same answer with the same structure, and that we should be "
                    "getting the audit view in the first meeting, not the fifth. He offered to "
                    "re-engage if we come back with a restated structure and a written opinion."
                ),
                "takeaways": (
                    "Derecognition failed under IFRS 9 — residual variability too high as structured",
                    "Provision stayed on balance sheet, so there was no capital release and no case",
                    "Gerald: 'the modelling was never the question'",
                    "He will re-engage if we return with a restated structure plus a written audit opinion",
                    "Any processor at their scale hits the same wall with this structure",
                ),
                "objections": (
                    "Cover sits on top of an unchanged provision rather than permitting release",
                ),
                "questions": (
                    "Can the structure be restated as a true risk transfer that survives IFRS 9?",
                ),
                "commitments": (
                    "Leslie to come back only once we have a written accounting opinion",
                ),
            },
        ),
        "next_steps": (
            {
                "title": "Restate the structure as a true risk transfer under IFRS 9",
                "detail": "Work with structuring counsel and a Big Four technical accounting team to "
                          "get derecognition to hold — most likely by moving more of the residual "
                          "variability to us rather than capping our exposure so tightly. Nothing else "
                          "on this deal matters until that is settled.",
                "owner": "Leslie Chacko", "due": "2026-09-15", "priority": "high", "status": "blocked",
                "rationale": "The stated reason we lost. Gerald will re-engage on a restated structure.",
            },
            {
                "title": "Move the accounting question into meeting one, everywhere",
                "detail": "Add 'has your audit team seen a structure like this, and would it permit "
                          "provision release' to the qualification script for every open deal. Nuvei "
                          "is at proposal with the same question still unanswered — that is the same "
                          "loss forming again.",
                "owner": "Leslie Chacko", "due": "2026-08-01", "priority": "high", "status": "todo",
                "rationale": "We spent four meetings on model performance before asking the question "
                             "that decided the outcome. Nuvei is currently repeating it.",
            },
            {
                "title": "Publish the accounting-treatment note as sales collateral",
                "detail": "Turn the eventual written opinion into a one-pager risk committees can hand "
                          "their auditors. It converts our biggest objection into a differentiator.",
                "owner": "Leslie Chacko", "due": "2026-09-30", "priority": "medium", "status": "todo",
                "rationale": "Every principal member will ask this. Being first with a clean answer is "
                             "worth more than any model improvement.",
            },
        ),
        "highlights": (
            ("blocker", "Lost on IFRS 9 derecognition: cover sat on top of the provision instead of "
                        "permitting release, so no capital was freed", 0.97),
            ("risk", "The same structure will fail at every principal member of comparable scale "
                     "until it is restated", 0.92),
            ("risk", "We validated the model for four meetings before testing the gate that decided it", 0.9),
            ("strength", "Champion stayed constructive and will re-engage on a restated structure", 0.7),
            ("signal", "Nuvei is at proposal with the same accounting question still open", 0.88),
        ),
    },
    {
        "company": "primer",
        "person": {
            "name": "Sofia Ferreira", "title": "Head of Merchant Acquiring", "role": "Head of Merchant Acquiring",
            "email": "sofia.ferreira@primer.io", "city": "London", "country": "UK",
        },
        "deal": {
            "stage": "discovery", "health": "stalled", "probability": 15, "value_usd": 210000,
            "expected_close": "2026-10-02", "source_channel": "linkedin", "opened_days": 31,
            "summary": (
                "Opened well, then went quiet — one good call 31 days ago and two unanswered "
                "follow-ups. The structural problem is that Primer is an orchestration layer: "
                "merchant credit risk sits with the acquirers they route to, not with Primer. "
                "Sofia was candid about that herself. Genuinely interesting as a channel "
                "partner into their acquirer network, but as a direct buyer the fit is weak. "
                "Worth one reframe attempt as a partnership, then disqualify as a direct deal."
            ),
        },
        "meetings": (
            {
                "title": "Intro call", "kind": "discovery", "days_ago": 31,
                "duration": 30, "sentiment": "neutral",
                "attendees": "Sofia Ferreira, Leslie Chacko",
                "summary": (
                    "Sofia was generous with time but the fit is thinner than the signal suggested. "
                    "Primer orchestrates payments across acquirers; the merchant credit risk and the "
                    "reserve requirement sit with those acquirers, not with Primer. She said so "
                    "plainly. She did float that several of her acquirer partners complain about "
                    "exactly this problem and offered an introduction — which has not materialised "
                    "across two follow-ups."
                ),
                "takeaways": (
                    "Primer is an orchestration layer — merchant credit risk sits with its acquirers",
                    "Sofia named the fit problem herself, unprompted and accurately",
                    "Offered intros to acquirer partners who do carry the risk; hasn't delivered",
                    "Possible channel play rather than a direct sale",
                ),
                "objections": ("'We route the volume, we don't hold the merchant risk'",),
                "questions": ("Would you work with our acquirer partners directly?",),
                "commitments": ("Sofia to introduce two acquirer partners",),
            },
        ),
        "next_steps": (
            {
                "title": "Reframe as a channel partnership, not a direct sale",
                "detail": "Sofia correctly identified that Primer doesn't hold the risk. Stop selling to "
                          "her and ask for the thing she already offered: intros to the acquirers in her "
                          "network who do. That converts a dead deal into pipeline.",
                "owner": "Leslie Chacko", "due": "2026-07-31", "priority": "high", "status": "todo",
                "rationale": "The only version of this opportunity that can actually close.",
            },
            {
                "title": "Chase the two acquirer introductions directly",
                "detail": "She offered these on the call and hasn't followed through across two nudges. "
                          "Make it trivially easy — send a two-line forwardable blurb rather than asking "
                          "her to compose anything.",
                "owner": "Leslie Chacko", "due": "2026-07-29", "priority": "medium", "status": "todo",
                "rationale": "Cheapest possible re-entry, and the intros are the actual prize.",
            },
            {
                "title": "Close as no-fit direct, keep as channel if no reply in 10 days",
                "detail": "If neither the reframe nor the intros land, mark the direct opportunity "
                          "disqualified on structural fit and move Sofia to the partner nurture list.",
                "owner": "Leslie Chacko", "due": "2026-08-10", "priority": "low", "status": "todo",
                "rationale": "31 days open, one meeting, no second contact — the pattern is clear.",
            },
        ),
        "highlights": (
            ("blocker", "Orchestration model means merchant credit risk sits with their acquirers, not them", 0.91),
            ("risk", "No contact in 18 days across two follow-up attempts", 0.88),
            ("risk", "Contact owns acquiring relationships, not a risk or capital budget", 0.79),
            ("signal", "Offered intros to acquirer partners who do carry the risk — real channel value", 0.66),
        ),
    },
)


def _iso_days_ago(days: float) -> str:
    return (BASE - timedelta(days=days)).date().isoformat()


def days_from_now(days: float, hour: int = 10) -> datetime:
    """A genuinely future timestamp, anchored to the real clock rather than BASE
    (which is a fixed point in the seeded past)."""
    target = datetime.now(timezone.utc) + timedelta(days=days)
    return target.replace(hour=hour, minute=0, second=0, microsecond=0)


def _seed_deals(db: Session, ws: Workspace, companies: list[Company], campaigns: list[Campaign]) -> None:
    """Create the post-first-meeting deal pipeline for the demo workspace."""
    by_slug = {c.slug: c for c in companies}
    active = [c for c in campaigns if c.status == "active"] or campaigns

    for i, spec in enumerate(DEAL_SEEDS):
        company = by_slug.get(spec["company"])
        if company is None:
            continue
        ps, ds = spec["person"], spec["deal"]
        opened = ds["opened_days"]
        camp = active[i % len(active)]
        email_seq = next(s for s in camp.sequences if s.channel == "email")

        person = Person(
            workspace_id=ws.id, company_id=company.id, name=ps["name"], title=ps["title"],
            role_category=ps["role"],
            linkedin_url=f"https://www.linkedin.com/in/{ps['name'].lower().replace(' ', '-')}",
            confidence=0.96, email=ps["email"], email_status="verified", email_source="apollo",
            apollo_id=f"apollo_{700000 + i}", city=ps["city"], country=ps["country"], enriched=True,
        )
        db.add(person)
        db.flush()

        db.add(Event(
            workspace_id=ws.id, person_id=person.id, company_id=company.id,
            type="decision_maker_found", channel=None,
            title=f"Identified as {ps['role']} at {company.name}",
            detail=f"Scout/Detective matched {person.name} to the {ps['role']} role with 96% confidence.",
            created_at=days_ago(opened + 6),
        ))

        # Outreach that produced the meeting, then the deal.
        db.add(Enrollment(
            workspace_id=ws.id, campaign_id=camp.id, sequence_id=email_seq.id,
            channel=ds["source_channel"], person_id=person.id,
            current_step=min(2, len(email_seq.steps)), status="in_deal",
            next_action_at=None, last_action_at=days_ago(spec["meetings"][0]["days_ago"]),
            replied_at=days_ago(opened + 1), enrolled_at=days_ago(opened + 5),
        ))

        first = email_seq.steps[0]
        # Same principal-vs-sponsored fork the generated threads use.
        v = _variant_for(first, person)
        db.add(Message(
            workspace_id=ws.id, person_id=person.id, campaign_id=camp.id, sequence_id=email_seq.id,
            channel="email", direction="outbound", step_name=first.name,
            subject=_fill(_subject_for(person, v.subject_template or ""), person),
            body=_fill(v.body_template, person, footer=True),
            status="replied", at=days_ago(opened + 5),
        ))
        db.add(Message(
            workspace_id=ws.id, person_id=person.id, campaign_id=camp.id, sequence_id=email_seq.id,
            channel="email", direction="inbound", step_name="Reply",
            subject=f"Re: {_fill(_subject_for(person, v.subject_template or ''), person)}",
            body=_reply_body("interested", person), reply_class="interested",
            at=days_ago(opened + 1),
        ))
        db.add(Event(
            workspace_id=ws.id, person_id=person.id, company_id=company.id, type="email_replied",
            channel="email", title="Replied — interested", detail=_reply_body("interested", person),
            meta=camp.name, created_at=days_ago(opened + 1),
        ))

        deal = Deal(
            workspace_id=ws.id, person_id=person.id, company_id=company.id, campaign_id=camp.id,
            stage=ds["stage"], health=ds["health"], probability=ds["probability"],
            value_usd=ds["value_usd"], owner="Leslie Chacko", source_channel=ds["source_channel"],
            summary=ds["summary"], opened_at=days_ago(opened),
            expected_close=ds["expected_close"],
            last_activity_at=days_ago(min(m["days_ago"] for m in spec["meetings"])),
        )

        for order, s in enumerate(spec["next_steps"], start=1):
            deal.next_steps.append(DealNextStep(
                step_order=order, title=s["title"], detail=s["detail"], owner=s["owner"],
                due_date=s["due"], priority=s["priority"], status=s["status"],
                rationale=s["rationale"],
            ))
        for kind, text, conf in spec["highlights"]:
            deal.highlights.append(DealHighlight(kind=kind, text=text, confidence=conf))

        db.add(deal)
        db.flush()

        # Meetings that already happened, each with its Closer write-up.
        for m in spec["meetings"]:
            meeting = ContactMeeting(
                workspace_id=ws.id, person_id=person.id, deal_id=deal.id,
                title=m["title"], kind=m["kind"], status="completed",
                occurred_at=days_ago(m["days_ago"]), duration_min=m["duration"],
                attendees=m["attendees"], location="https://meet.example/vector-intro",
                sentiment=m["sentiment"], summary=m["summary"], source="gemini",
                recording_url=f"https://meet.example/rec/{company.slug}-{m['kind']}",
            )
            for kind, key in (
                ("takeaway", "takeaways"), ("objection", "objections"),
                ("question", "questions"), ("commitment", "commitments"),
            ):
                for text in m.get(key, ()):
                    meeting.points.append(MeetingPoint(kind=kind, text=text))
            db.add(meeting)

            db.add(Event(
                workspace_id=ws.id, person_id=person.id, company_id=company.id,
                type="meeting_held", channel=ds["source_channel"], title=m["title"],
                detail=f"{m['duration']}-min {m['kind']} call · {m['sentiment']}",
                meta=camp.name, created_at=days_ago(m["days_ago"]),
            ))

        # The next one on the calendar — shows the scheduled state (no summary yet).
        upcoming = spec.get("upcoming")
        if upcoming:
            db.add(ContactMeeting(
                workspace_id=ws.id, person_id=person.id, deal_id=deal.id,
                title=upcoming["title"], kind=upcoming["kind"], status="scheduled",
                occurred_at=days_from_now(upcoming["days_ahead"]), duration_min=upcoming["duration"],
                attendees=upcoming["attendees"], location="https://meet.example/vector-intro",
                source="manual",
            ))
            db.add(Event(
                workspace_id=ws.id, person_id=person.id, company_id=company.id,
                type="meeting_booked", channel=ds["source_channel"], title=upcoming["title"],
                detail=f"{upcoming['duration']}-min {upcoming['kind']} call scheduled",
                meta=camp.name, created_at=days_ago(1),
            ))

        db.add(Event(
            workspace_id=ws.id, person_id=person.id, company_id=company.id, type="deal_opened",
            channel=ds["source_channel"], title=f"Deal opened — {ds['stage'].replace('_', ' ')}",
            detail=f"${ds['value_usd']:,}/yr facility fee · {ds['probability']}% · close {ds['expected_close']}",
            meta=camp.name, created_at=days_ago(opened),
        ))

    # A contact with a meeting but NO deal — proves the Meetings tab is not
    # gated on the deal pipeline.
    booked = db.scalar(
        select(Person)
        .join(Enrollment, Enrollment.person_id == Person.id)
        .where(Person.workspace_id == ws.id, Enrollment.status == "booked")
        .limit(1)
    )
    if booked is not None:
        db.add(ContactMeeting(
            workspace_id=ws.id, person_id=booked.id, title="Intro call",
            kind="intro", status="scheduled", occurred_at=days_from_now(2, hour=14), duration_min=30,
            attendees=f"{booked.name}, Leslie Chacko",
            location="https://meet.example/vector-intro", source="manual",
        ))


def seed_demo(db: Session) -> Workspace:
    """Create (or return existing) demo workspace, fully populated."""
    existing = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    if existing:
        return existing

    _reset()
    ws = Workspace(name="Konfyd", is_demo=True)
    db.add(ws)
    db.flush()

    db.add(User(
        workspace_id=ws.id, email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD),
        name="Leslie Chacko", role="Co-Founder & CEO", is_demo=True,
    ))

    companies: list[Company] = []
    people: list[Person] = []

    used_names: set[str] = {d["person"]["name"] for d in DEAL_SEEDS}

    for seed in COMPANY_SEEDS:
        name, slug, domain, industry, employees, location, carrier, deferred, buyable = seed
        primary = pick(SIGNAL_TYPES)
        disc = randint(1, 60)
        score = _icp_score(carrier, deferred, buyable, employees)
        tier = _tier(score)
        intent = _intent_score(primary, disc)
        rationale, matched, concerns = _icp_reasoning(
            name, industry, carrier, deferred, buyable, employees, primary
        )
        src = pick(SOURCES)

        company = Company(
            workspace_id=ws.id, name=name, slug=slug, website_url=f"https://{domain}",
            linkedin_url=f"https://www.linkedin.com/company/{slug}", industry=industry,
            employee_range=employees, location=location, signal_type=primary,
            reason_to_target=_reason(name, primary), confidence=round(0.62 + rand() * 0.33, 2),
            icp_score=score, icp_tier=tier, icp_rationale=rationale,
            intent_score=intent, signal_age_days=disc,
            qualified=score >= 35, source_radar="news", source_name=src,
            article_headline=_headline(name, primary), article_url=_article_url(src, slug, primary),
            # Published BEFORE we discovered it — Radar reads the press, it doesn't
            # pre-empt it.
            published_date=human_date(disc + randint(0, 3)), discovered_at=days_ago(disc),
        )
        for c in matched:
            company.criteria.append(ICPCriterion(kind="matched", text=c))
        for c in concerns:
            company.criteria.append(ICPCriterion(kind="concern", text=c))

        n_signals = randint(1, 3)
        for s in range(n_signals):
            st = primary if s == 0 else pick(SIGNAL_TYPES)
            sd = disc + s * randint(5, 25)
            ssrc = src if s == 0 else pick(SOURCES)
            company.signals.append(Signal(
                signal_type=st, reason_to_target=_reason(name, st), confidence=round(0.62 + rand() * 0.33, 2),
                article_headline=_headline(name, st), article_url=_article_url(ssrc, slug, st),
                published_date=human_date(sd + randint(0, 3)), source_name=ssrc, discovered_at=days_ago(sd),
            ))

        # Small sponsored shops have no CRO — risk appetite sits with the founder.
        role_pool = ROLES_BY_CARRIER.get(carrier) or (
            SMALL_COMPANY_ROLES + ROLES[:3] if employees in ("11-50", "51-200") else ROLES
        )
        n_dm = randint(1, 3)
        for di, role in enumerate(pick_n(role_pool, n_dm)):
            for _ in range(12):  # keep every person in the workspace unique
                fn, ln = pick(FIRST_NAMES), pick(LAST_NAMES)
                if f"{fn} {ln}" not in used_names:
                    break
            used_names.add(f"{fn} {ln}")
            has_email = chance(0.82)
            # `verified` is an assertion about reality — only the pattern+SMTP or a
            # provider can grant it, so weight it the way real enrichment lands.
            estatus = pick(["verified", "guessed", "guessed", "unverified"]) if has_email else None
            has_li = chance(0.85)
            person = Person(
                workspace_id=ws.id, name=f"{fn} {ln}", title=pick(TITLE_BY_ROLE[role]), role_category=role,
                linkedin_url=(f"https://www.linkedin.com/in/{fn.lower()}-{ln.lower()}" if has_li else ""),
                confidence=(round(0.85 + rand() * 0.14, 2) if di == 0 else round(0.3 + rand() * 0.5, 2)),
                # first.last@ — first-name-only aliases don't exist at these companies
                email=(f"{fn.lower()}.{ln.lower().replace('ü','u')}@{domain}" if has_email else None),
                email_status=estatus,
                email_source=(pick(EMAIL_SOURCES) if has_email else None),
                apollo_id=(f"apollo_{randint(100000, 999999)}" if chance(0.3) else None),
                city=(location.split(",")[0] if chance(0.4) else None),
                country=(location.split(",")[1].strip() if chance(0.4) and "," in location else None),
                enriched=has_email,
            )
            company.people.append(person)
            people.append(person)

        db.add(company)
        companies.append(company)

    db.flush()

    # Baseline "discovered" events for each person
    for p in people:
        db.add(Event(
            workspace_id=ws.id, person_id=p.id, company_id=p.company_id, type="decision_maker_found",
            channel=None, title=f"Identified as {p.role_category} at {p.company.name}",
            detail=f"Scout/Detective matched {p.name} to the {p.role_category} role with {round(p.confidence * 100)}% confidence.",
            created_at=days_ago(randint(1, 40)),
        ))

    # --- Campaigns: each with an email + linkedin sequence ---
    campaigns: list[Campaign] = []
    for d in CAMPAIGN_DEFS:
        camp = Campaign(
            workspace_id=ws.id, name=d["name"], description=d["desc"], status=d["status"],
            icp_min_score=d["min"], theme=d["theme"], created_at=days_ago(d["age"]),
        )
        email_seq = Sequence(campaign=camp, channel="email", name="Email sequence",
                             status=("active" if d["status"] == "active" else "draft"))
        li_seq = Sequence(campaign=camp, channel="linkedin", name="LinkedIn sequence",
                          status=("active" if d["status"] == "active" else "draft"))
        _build_email_steps(email_seq)
        _build_linkedin_steps(li_seq)
        camp.sequences = [email_seq, li_seq]
        db.add(camp)
        campaigns.append(camp)

    db.flush()

    def _seq(camp: Campaign, channel: str) -> Sequence:
        return next(s for s in camp.sequences if s.channel == channel)

    # --- Enrollments + messages + events ---
    for p in people:
        company = p.company
        # ONE campaign per person, driving both channels. A prospect must never be
        # in "post-raise" on email and "new CRO" on LinkedIn at the same time.
        eligible = [c for c in campaigns if company.icp_score >= c.icp_min_score]
        # The campaign must match the reason we surfaced the account. A high-risk
        # principal found via portfolio M&A does not belong in "Payfac Launch".
        want = ("sponsor-residual" if RISK_CARRIER_BY_SLUG.get(company.slug) == "sponsor_bank"
                else THEME_FOR_SIGNAL.get(company.signal_type))
        assigned = next((c for c in eligible if c.theme == want), None) or (pick(eligible) if eligible else None)

        # email enrollment
        if p.email and assigned and chance(0.8):
            if True:
                camp = assigned
                seq = _seq(camp, "email")
                status = pick(EMAIL_STATUS_POOL)
                n_steps = len(seq.steps)
                step = _status_to_step(status, n_steps)
                enrolled_days = randint(2, 30)
                enr = Enrollment(
                    workspace_id=ws.id, campaign_id=camp.id, sequence_id=seq.id, channel="email", person_id=p.id,
                    current_step=step, status=status,
                    next_action_at=(None if status in ("completed", "not_interested", "bounced", "booked") else days_ago(-randint(1, 5))),
                    last_action_at=days_ago(randint(1, enrolled_days)),
                    replied_at=(days_ago(randint(1, enrolled_days)) if status in ("replied", "in_conversation", "meeting", "booked") else None),
                    enrolled_at=days_ago(enrolled_days),
                )
                db.add(enr)
                db.flush()
                _email_thread(db, ws.id, p, camp, seq, step, status, enrolled_days)
        # linkedin enrollment — same campaign as email, so the story is consistent
        if p.linkedin_url and assigned and chance(0.55):
            if True:
                camp = assigned
                seq = _seq(camp, "linkedin")
                status = pick(LI_STATUS_POOL)
                n_steps = len(seq.steps)
                step = _li_status_to_step(status, n_steps)
                enrolled_days = randint(2, 25)
                accepted = status in ("accepted", "in_conversation", "meeting", "booked", "completed")
                enr = Enrollment(
                    workspace_id=ws.id, campaign_id=camp.id, sequence_id=seq.id, channel="linkedin", person_id=p.id,
                    current_step=step, status=status,
                    next_action_at=(None if status in ("completed", "not_interested", "invite_expired", "booked") else days_ago(-randint(1, 4))),
                    last_action_at=days_ago(randint(1, enrolled_days)),
                    replied_at=(days_ago(randint(1, enrolled_days)) if status in ("in_conversation", "meeting", "booked") else None),
                    enrolled_at=days_ago(enrolled_days),
                    invited_at=(days_ago(enrolled_days) if status != "pending" else None),
                    accepted_at=(days_ago(randint(1, enrolled_days)) if accepted else None),
                )
                db.add(enr)
                db.flush()
                _linkedin_thread(db, ws.id, p, camp, seq, step, status, enrolled_days)

    # Sponsor-bank -> sponsored-entity edges (the portfolio play).
    by_slug = {c.slug: c for c in companies}
    for sponsor_slug, sponsored in SPONSORSHIP.items():
        sponsor = by_slug.get(sponsor_slug)
        if sponsor is None:
            continue
        for sl in sponsored:
            target = by_slug.get(sl)
            if target is not None:
                db.add(Sponsorship(workspace_id=ws.id, sponsor_id=sponsor.id, sponsored_id=target.id))
    db.flush()

    # Closer stage — the post-first-meeting deal pipeline.
    _seed_deals(db, ws, companies, campaigns)
    db.flush()

    _seed_send_gate(db, ws, campaigns, people)

    db.commit()
    return ws


def _seed_send_gate(db: Session, ws: Workspace, campaigns: list[Campaign], people: list[Person]) -> None:
    """Every campaign starts in manual mode, so make the demo reflect that.

    Anyone already mid-sequence must have been approved at some point — stamp
    them launched. Then add a fresh batch still awaiting approval so the manual
    flow has something real to act on.
    """
    for e in db.scalars(select(Enrollment).where(Enrollment.workspace_id == ws.id)).all():
        if e.current_step >= 1 or e.status not in ("active", "pending"):
            e.launched_at = e.enrolled_at
            e.launched_by = "Leslie Chacko"

    # A fresh intake batch: enrolled, nothing sent, held for approval.
    already = {
        (e.person_id, e.channel)
        for e in db.scalars(select(Enrollment).where(Enrollment.workspace_id == ws.id)).all()
    }
    active = [c for c in campaigns if c.status == "active"] or campaigns
    added = 0
    for p in people:
        if added >= 9:
            break
        company = p.company
        eligible = [c for c in active if company and company.icp_score >= c.icp_min_score]
        if not eligible:
            continue
        camp = eligible[added % len(eligible)]
        channel = "email" if (p.email and added % 3 != 2) else "linkedin"
        if channel == "linkedin" and not p.linkedin_url:
            continue
        if (p.id, channel) in already:
            continue
        seq = next(s for s in camp.sequences if s.channel == channel)
        db.add(Enrollment(
            workspace_id=ws.id, campaign_id=camp.id, sequence_id=seq.id, channel=channel,
            person_id=p.id, current_step=0,
            status="active" if channel == "email" else "pending",
            next_action_at=None, last_action_at=None,
            enrolled_at=days_ago(randint(0, 2)),
        ))
        already.add((p.id, channel))
        added += 1


def _status_to_step(status, max_steps):
    if status == "active":
        return randint(1, max(1, max_steps - 1))
    if status == "completed":
        return max_steps
    if status == "bounced":
        return 1
    return randint(1, max_steps)


def _li_status_to_step(status, max_steps):
    if status == "pending":
        return 0
    if status in ("invite_sent", "invite_expired"):
        return 1
    if status == "completed":
        return max_steps
    return randint(2, max_steps)


def _step_subject(i, step, steps, person: Person, variant) -> str:
    """Subject per step, so a thread doesn't repeat one line four times.

    Step 1 leads with the signal that surfaced the account. Step 3 asks its own
    short question (a new subject earns a re-open). Steps 2 and 4 are follow-ups
    in the same thread, so they carry Re: of the opener — a real reply chain, not
    the fabricated Re: on a cold send.
    """
    opener = _subject_for(person, steps[0].variants[0].subject_template or "")
    if i == 0:
        return _subject_for(person, variant.subject_template or "")
    if step.name == "Short bump":
        return variant.subject_template or opener
    return f"Re: {opener}"


def _email_thread(db, ws_id, person, camp, seq, step, status, enrolled_days):
    steps = seq.steps
    for i in range(step):
        s = steps[i]
        # Step 1 forks on principal vs sponsored; later steps have one variant.
        v = _variant_for(s, person) if i == 0 else s.variants[0]
        subj = _fill(_step_subject(i, s, steps, person, v), person)
        day = max(1, enrolled_days - i * 3)
        db.add(Message(
            workspace_id=ws_id, person_id=person.id, campaign_id=camp.id, sequence_id=seq.id,
            channel="email", direction="outbound", step_name=s.name, subject=subj,
            body=_fill(v.body_template, person, footer=True),
            status=("opened" if i < step - 1 else "sent"), at=days_ago(day),
        ))
        db.add(Event(
            workspace_id=ws_id, person_id=person.id, company_id=person.company_id, type="email_sent",
            channel="email", title=f"Email sent — {s.name}", detail=subj, meta=camp.name, created_at=days_ago(day),
        ))
    if status in ("replied", "in_conversation", "meeting", "booked"):
        rc = "not_interested" if status == "not_interested" else pick(["interested", "objection", "referral"])
        body = _reply_body(rc, person)
        db.add(Message(
            workspace_id=ws_id, person_id=person.id, campaign_id=camp.id, sequence_id=seq.id, channel="email",
            direction="inbound", step_name="Reply",
            subject=f"Re: {_fill(_subject_for(person, steps[0].variants[0].subject_template or ''), person)}",
            body=body, reply_class=rc, at=days_ago(randint(1, enrolled_days)),
        ))
        db.add(Event(
            workspace_id=ws_id, person_id=person.id, company_id=person.company_id, type="email_replied",
            channel="email", title=f"Replied — {rc.replace('_', ' ')}", detail=body, meta=camp.name,
            created_at=days_ago(randint(1, enrolled_days)),
        ))
    if status in ("meeting", "booked"):
        db.add(Event(
            workspace_id=ws_id, person_id=person.id, company_id=person.company_id, type="meeting_booked",
            channel="email", title="Intro call booked", detail=f"30-min intro call scheduled with {person.name}.",
            meta=camp.name, created_at=days_ago(randint(1, 5)),
        ))


def _linkedin_thread(db, ws_id, person, camp, seq, step, status, enrolled_days):
    steps = seq.steps
    for i in range(step):
        s = steps[i]
        v = s.variants[0]
        day = max(1, enrolled_days - i * 3)
        db.add(Message(
            workspace_id=ws_id, person_id=person.id, campaign_id=camp.id, sequence_id=seq.id, channel="linkedin",
            direction="outbound", step_name=s.name, body=_fill(v.body_template, person), status="sent", at=days_ago(day),
        ))
        db.add(Event(
            workspace_id=ws_id, person_id=person.id, company_id=person.company_id,
            type=("linkedin_invite_sent" if s.kind == "invite" else "note"), channel="linkedin",
            title=("LinkedIn invite sent" if s.kind == "invite" else f"LinkedIn message — {s.name}"),
            detail=_fill(v.body_template, person), meta=camp.name, created_at=days_ago(day),
        ))
    if status in ("accepted", "in_conversation", "meeting", "booked", "completed"):
        db.add(Event(
            workspace_id=ws_id, person_id=person.id, company_id=person.company_id, type="linkedin_accepted",
            channel="linkedin", title="LinkedIn invite accepted", detail=f"{person.name} accepted the connection request.",
            meta=camp.name, created_at=days_ago(randint(1, enrolled_days)),
        ))
    if status in ("in_conversation", "meeting", "booked"):
        db.add(Message(
            workspace_id=ws_id, person_id=person.id, campaign_id=camp.id, sequence_id=seq.id, channel="linkedin",
            direction="inbound", step_name="Reply", body=_reply_body("interested", person), reply_class="interested",
            at=days_ago(randint(1, enrolled_days)),
        ))
