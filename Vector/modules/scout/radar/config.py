"""Radar configuration — the single source of truth for what Radar targets.

Holds three things:
  1. NEWS_SOURCES    — news websites + how to page through their listings
  2. HIRING_SOURCES  — hiring / careers pages (used later by HiringRadar)
  3. COMPANY_PROFILE — who *we* are and who our ideal customer is (ICP), used
                       by the ICP rating agent to score every lead.

Edit this file to point Radar at new sources or to refine the ICP.

---------------------------------------------------------------------------
Research notes (Konfyd) — why these sources / this ICP
---------------------------------------------------------------------------
Konfyd (konfyd.com, Miami, founded 2023 by Leslie Chacko and Anthony Reversat;
backed by Blumberg Capital, HTwenty Capital, Invariantes Fund and SaaS Ventures)
sells CAPITAL MARKETS + MERCHANT RISK infrastructure to payment processors and
merchant acquirers. Its own framing: "capital markets solutions to drive
growth", helping processors "unleash topline growth" and "de-risk merchant
portfolios".

The mechanic that makes this a real market: an acquirer is the guarantor of
last resort for every merchant on its book. When a merchant goes insolvent or
can't fund its chargebacks, the liability lands on the acquirer. To cover that
tail risk, processors post collateral to their sponsor or the schemes, hold
merchant reserves and demand rolling deposits — which (a) locks up balance sheet, (b) forces them to
decline exactly the high-margin/high-risk segments they'd most like to win, and
(c) pushes cost onto merchants. Konfyd predicts insolvency events earlier and
moves that risk off the processor's balance sheet, so capital is released and
the portfolio can grow.

That means a lead is in-market when something has just moved its risk exposure
or its cost of capital:
  * raised funding / IPO'd / been acquired  → growth targets meet capital limits
  * expanded into a new geography or vertical → new, unpriced risk
  * launched payfac-as-a-service / embedded payments → they now underwrite SMBs
  * hired a Chief Risk Officer or Head of Underwriting → mandate to re-tool
  * card-network rule changes on chargeback/refund thresholds
  * a large merchant collapse in travel, ticketing, retail or subscriptions
    → acquirers eat the disputes, and everyone re-reads their reserve policy

Sources below were chosen by *probing* each candidate with this project's own
fetcher (modules/scout/radar/NewsRadar/fetcher.py) and counting real article
links on the rendered HTML — not by reputation. Results:

  Digital Transactions   20-25 articles/page, deep pagination verified to p20.
                         The merchant-acquiring trade press; densest source of
                         acquirer/ISO/payfac news anywhere. PRIMARY.
  PYMNTS                 ~10-14/page, deep pagination verified to p15. Largest
                         payments newsroom by volume.
  Payments Dive          ~30/page, but pagination 403s intermittently under
                         load → configured as explicit pages, not a template.
  Finextra               12/page; pages beyond ~3 return errors even with a
                         delay → capped at 3.
  Fintech Futures        Payments desk, server-rendered, paginates cleanly.
  FinSMEs                Near-pure funding wire; the fintech category is a
                         cheap way to catch raises the trade press misses.
  TechCrunch — Fintech    Mainstream fintech funding coverage.
  Tearsheet              Payments/embedded-finance analysis.

Rejected: The Paypers (listing rendered client-side — 0 links to a plain
fetch), Payment Expert and Electronic Payments International (403 to a
non-browser client). Re-add only behind a headless browser.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from modules.common import control

# Controlling knobs now live in modules/common/control.py (single control panel).
# Radar walks a source's pagination from page 1 up to this many pages, unless the
# source overrides it with its own `max_pages`.
MAX_PAGES = control.RADAR_MAX_PAGES


@dataclass(frozen=True)
class NewsSource:
    """A news website Radar should scan for lead signals.

    Provide pages as an explicit ``listing_urls`` list and/or a ``page_template``
    containing ``{page}`` (e.g. ``https://site.com/news/page/{page}/``). Radar
    paginates the template from page 1 up to ``max_pages`` (falling back to the
    global MAX_PAGES), stopping early once enough leads are found. Relative
    article links are resolved against the actual page URL being scanned.

    ``max_pages`` exists because pagination depth is a per-site fact: some
    outlets serve 20+ pages happily, others start refusing after 3.
    """

    name: str
    page_template: str | None = None               # e.g. "https://site.com/news/page/{page}/"
    listing_urls: tuple[str, ...] = ()             # explicit page URLs (no pagination)
    enabled: bool = True
    max_pages: int | None = None                   # per-source cap; None = MAX_PAGES

    def iter_pages(self) -> Iterator[str]:
        """Yield explicit listing URLs, then template pages 1 .. max_pages."""
        yield from self.listing_urls
        if self.page_template:
            limit = self.max_pages or MAX_PAGES
            for page in range(1, limit + 1):
                yield self.page_template.format(page=page)


# ---------------------------------------------------------------------------
# 1. News sources  (headlines here become lead signals)
# ---------------------------------------------------------------------------
# Chosen for Konfyd's ICP: payment processors, PSPs, merchant acquirers, payfacs,
# ISOs and payment-orchestration platforms that carry merchant credit risk.
# Ordered best-first — Radar finishes one source before moving to the next, so
# the densest acquiring-specific feeds come first.
NEWS_SOURCES: tuple[NewsSource, ...] = (
    # Digital Transactions — the acquiring/ISO/payfac trade publication. Highest
    # signal-per-article of anything probed: processor deals, portfolio moves,
    # underwriting and chargeback coverage.
    NewsSource(
        name="Digital Transactions — News",
        page_template="https://www.digitaltransactions.net/category/news/page/{page}/",
        max_pages=25,
    ),
    # PYMNTS — largest payments newsroom; broad but very high volume.
    NewsSource(
        name="PYMNTS — News",
        page_template="https://www.pymnts.com/category/news/page/{page}/",
        max_pages=20,
    ),
    NewsSource(
        name="PYMNTS — Merchant Innovation",
        page_template="https://www.pymnts.com/category/news/merchant-innovation/page/{page}/",
        max_pages=15,
    ),
    # Payments Dive — strong US business-of-payments desk. Pagination is rate
    # limited, so we take the first few pages explicitly rather than walking.
    NewsSource(
        name="Payments Dive",
        listing_urls=(
            "https://www.paymentsdive.com/",
            "https://www.paymentsdive.com/?page=2",
            "https://www.paymentsdive.com/?page=3",
        ),
    ),
    # Finextra — fintech funding, payments and regulation. Shallow pagination.
    NewsSource(
        name="Finextra — Latest",
        page_template="https://www.finextra.com/latest-news?page={page}",
        max_pages=3,
    ),
    # Fintech Futures — payments desk, good on processor/acquirer partnerships.
    NewsSource(
        name="Fintech Futures — Payments",
        page_template="https://www.fintechfutures.com/category/payments/page/{page}/",
        max_pages=12,
    ),
    # FinSMEs — near-pure funding wire ("X raises $Y"). Cheap raise detection.
    NewsSource(
        name="FinSMEs — Fintech",
        page_template="https://www.finsmes.com/category/fintech/page/{page}/",
        max_pages=12,
    ),
    # TechCrunch — mainstream fintech funding coverage.
    NewsSource(
        name="TechCrunch — Fintech",
        page_template="https://techcrunch.com/category/fintech/page/{page}/",
        max_pages=10,
    ),
    # Tearsheet — payments / embedded finance analysis.
    NewsSource(
        name="Tearsheet — Payments",
        page_template="https://tearsheet.co/category/payments/page/{page}/",
        max_pages=8,
    ),

    # ---- Signal sources that beat the trade press -------------------------
    # SEC EDGAR full-text search. The highest-intent source available: a public
    # processor's OWN filing, giving its merchant-loss reserve as a dated number.
    # A YoY increase is a pre-built business case with a citation.
    NewsSource(
        name="SEC EDGAR — Merchant Loss Reserves",
        listing_urls=(
            'https://efts.sec.gov/LATEST/search-index?q=%22reserve+for+merchant+losses%22&forms=10-Q,10-K',
            'https://efts.sec.gov/LATEST/search-index?q=%22allowance+for+merchant+losses%22&forms=10-Q,10-K',
            'https://efts.sec.gov/LATEST/search-index?q=%22settlement+processing+obligations%22&forms=10-Q,10-K',
            'https://efts.sec.gov/LATEST/search-index?q=%22chargeback+guarantee%22&forms=10-Q,10-K',
        ),
    ),
    # Card-network rule bulletins. An acquirer entering VAMP or Mastercard ECP has
    # a deadline set by someone other than us — the loudest signal in the industry.
    NewsSource(
        name="Visa Business News — Rules & Programmes",
        listing_urls=("https://usa.visa.com/support/consumer/visa-rules.html",),
    ),
    # Merchant failures, sourced properly. The Gazette carries UK administrations;
    # Retail Dive tracks US retail bankruptcies. Both are upstream of the loss
    # landing on an acquirer.
    NewsSource(
        name="The Gazette — Insolvency Notices",
        page_template="https://www.thegazette.co.uk/all-notices/notice?categorycode-lt=G205&page={page}",
        max_pages=6,
    ),
    NewsSource(
        name="Retail Dive — Bankruptcy",
        listing_urls=(
            "https://www.retaildive.com/topic/bankruptcy/",
            "https://www.retaildive.com/topic/bankruptcy/?page=2",
        ),
    ),
)


# ---------------------------------------------------------------------------
# 2. Hiring sources  (reserved for HiringRadar)
# ---------------------------------------------------------------------------
# A processor posting "Head of Merchant Risk" or "Merchant Underwriting Manager"
# is one of the strongest buying signals Konfyd has: it says underwriting is being
# scaled by headcount, which is exactly the constraint we remove. These are the
# queries HiringRadar runs — populated rather than left as a comment, so the
# `hiring` signal in ideal_signals has an actual source behind it.
HIRING_SOURCES: tuple[dict, ...] = (
    {"name": "LinkedIn Jobs — Merchant Risk",
     "url": "https://www.linkedin.com/jobs/search/?keywords=%22merchant%20risk%22%20OR%20%22merchant%20underwriting%22"},
    {"name": "LinkedIn Jobs — Chief Credit Officer, Payments",
     "url": "https://www.linkedin.com/jobs/search/?keywords=%22chief%20credit%20officer%22%20payments"},
    {"name": "Indeed — Merchant Underwriting",
     "url": "https://www.indeed.com/jobs?q=%22merchant+underwriting%22"},
    # Titles that, when newly posted, mean reserve policy is being rebuilt.
    {"name": "_target_titles",
     "titles": ("Head of Merchant Risk", "Merchant Underwriting Manager",
                "Chief Credit Officer", "Head of Portfolio Risk",
                "Head of Settlement Risk", "VP Merchant Underwriting")},
)


# ---------------------------------------------------------------------------
# 3. Our company + Ideal Customer Profile (ICP)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CompanyProfile:
    """Describes us and our ideal customer, so leads can be scored for fit."""

    # About us
    company_name: str
    what_we_sell: str
    value_proposition: str

    # Ideal customer
    target_industries: tuple[str, ...]
    target_company_sizes: tuple[str, ...]        # e.g. "11-50", "51-200", "201-1000"
    target_geographies: tuple[str, ...]
    target_personas: tuple[str, ...]             # buyer roles/titles
    ideal_signals: tuple[str, ...]               # events that make a company timely to reach
    disqualifiers: tuple[str, ...] = field(default_factory=tuple)

    def as_prompt(self) -> str:
        """Render the profile as a compact block for LLM prompts."""
        return (
            f"OUR COMPANY: {self.company_name}\n"
            f"WHAT WE SELL: {self.what_we_sell}\n"
            f"VALUE PROPOSITION: {self.value_proposition}\n"
            f"TARGET INDUSTRIES: {', '.join(self.target_industries)}\n"
            f"TARGET COMPANY SIZES: {', '.join(self.target_company_sizes)}\n"
            f"TARGET GEOGRAPHIES: {', '.join(self.target_geographies)}\n"
            f"TARGET BUYER PERSONAS: {', '.join(self.target_personas)}\n"
            f"IDEAL BUYING SIGNALS: {', '.join(self.ideal_signals)}\n"
            f"DISQUALIFIERS: {', '.join(self.disqualifiers) or 'none'}"
        )


COMPANY_PROFILE = CompanyProfile(
    company_name="Konfyd",
    what_we_sell=(
        "Capital markets and merchant-risk infrastructure for payment "
        "processors and merchant acquirers. Konfyd predicts merchant "
        "insolvency and deferred-delivery events before they happen, prices "
        "that tail risk, and takes it off the processor's balance sheet as a "
        "rated counterparty — cutting merchant reserves, rolling deposits and "
        "the collateral posted to sponsor banks and the schemes, so the "
        "portfolio can grow instead of being rationed. NOTE for scoring: "
        "regulatory own funds (PSD2 Art. 9 Method A/B/C, US state MTL net "
        "worth) scale off payment volume and are NOT reducible by transferring "
        "merchant credit risk — only merchant-risk collateral is."
    ),
    value_proposition=(
        "For a principal scheme member, the processor is the guarantor of last "
        "resort for every merchant on its book. For a payfac or PSP operating "
        "under someone else's membership, the sponsor bank holds the paper but "
        "the loss flows back through the sponsorship agreement — usually "
        "against a blanket collateral formula the payfac had no say in. Either "
        "way the exposure that hurts is deferred delivery: the stock of "
        "paid-but-undelivered obligations. When a travel, ticketing or events "
        "merchant fails, months of forward bookings arrive as disputes at once. "
        "Konfyd turns that unpriced tail risk into something measured and "
        "transferable, so processors can approve the high-margin segments they "
        "currently decline and release the capital sitting behind reserves."
    ),
    target_industries=(
        "Payment processors / merchant acquirers",
        "Payment service providers (PSPs) and payment gateways",
        "Payment facilitators (payfacs) and payfac-as-a-service platforms",
        "ISOs, ISVs and independent sales organisations",
        "Payment orchestration platforms",
        "Acquiring banks and sponsor banks",
        "Embedded payments / vertical SaaS with an in-house payments arm",
        "Marketplaces and platforms that settle funds to sellers",
        "BNPL and merchant-cash-advance providers carrying merchant credit risk",
    ),
    target_company_sizes=("51-200", "201-1000", "1001-5000", "5000+"),
    target_geographies=(
        "United States", "Canada", "United Kingdom", "European Union",
        "LATAM", "Singapore", "Australia",
    ),
    # Ordered by who actually owns the decision. Note: at a processor, "Chief Risk
    # Officer" often means fraud/AML rather than merchant credit — Detective must
    # disambiguate on profile text, not title alone.
    target_personas=(
        "Chief Risk Officer (merchant credit, NOT fraud/AML)",
        "Chief Credit Officer / Head of Credit Risk — owns credit committee",
        "Head of Merchant Risk / Head of Portfolio Risk / Head of Settlement Risk",
        "VP Merchant Underwriting / Head of Underwriting",
        "Treasurer / Head of Treasury / Head of Capital Markets — owns posted collateral",
        "Chief Financial Officer",
        "CEO or COO of a sponsored payfac under ~200 people (no CRO exists yet)",
        "Head of Merchant Sponsorship / Head of Payments Risk (at sponsor banks)",
        "Head of Merchant Acquiring — ally for the declined-revenue angle, not the buyer",
    ),
    # Ordered by real intent. The top four are the ones that come with a deadline
    # and a budget; the funding/award end of the list is timing garnish.
    ideal_signals=(
        "entered Visa VAMP (Acquirer Monitoring) or Mastercard ECP/ECM — an acquirer-level "
        "dispute-ratio breach carries a board-mandated deadline and a budget",
        "10-K/10-Q movement in 'reserve for merchant losses', 'allowance for merchant losses', "
        "'settlement processing obligations' or 'chargeback guarantees' — a dated, public number",
        "changed sponsor bank or BIN sponsorship — collateral terms renegotiated from scratch",
        "a large merchant in their portfolio entered insolvency / Chapter 11 / administration, "
        "especially one with forward bookings (travel, ticketing, events, subscriptions)",
        "acquired a merchant portfolio, ISO or PSP — inherited risk they did not underwrite",
        "hired a Chief Risk Officer, Chief Credit Officer or Head of Merchant Risk",
        "regulator enforcement or consent order affecting a sponsor bank, forcing downstream "
        "collateral increases",
        "launched payfac-as-a-service, embedded payments or a new merchant-onboarding product",
        "moved into a high-risk vertical — travel, ticketing, events, subscriptions, iGaming, crypto",
        "expanded acquiring into a new country or region with no local loss history",
        "raised a securitisation, warehouse or debt facility, or drew a rating action — they are "
        "actively optimising cost of capital",
        "raised growth equity, IPO'd or was taken private (balance-sheet scrutiny)",
    ),
    disqualifiers=(
        "consumer-only fintech with no merchant acquiring or settlement exposure",
        "issuing-only card programmes that carry no merchant credit risk",
        "pure crypto exchanges and wallets with no card acquiring",
        "direct competitors (merchant-risk scoring, acquirer chargeback insurance, reserve-replacement providers)",
        "single-merchant retailers and brands (they are the merchant, not the acquirer)",
        "banks with no merchant-acquiring or sponsorship line of business",
        "pre-product / idea-stage companies with no live payment volume",
        "non-profit / government payment schemes",
    ),
)


# ---------------------------------------------------------------------------
# Tiered LLMs for Radar's agents
# ---------------------------------------------------------------------------
# Two tiers keep cost down without sacrificing quality where it matters:
#   NORMAL      — high-volume, lower-complexity work (selector inference, lead triage)
#   HIGH_EFFORT — the hard reasoning step (ICP qualification)
#
# We default to Claude: Gemini's free tier is heavily rate-limited (5 req/min)
# and 2.5-pro is unavailable on it. To use Gemini instead (e.g. on a paid plan),
# switch these to {"provider": "gemini", "model": "gemini-2.5-flash"} etc.
NORMAL_LLM = control.NORMAL_LLM
HIGH_EFFORT_LLM = control.HIGH_EFFORT_LLM

# Only persist leads that meet this ICP score (0-100). Set to 0 to keep everything.
MIN_ICP_SCORE = control.RADAR_MIN_ICP_SCORE

# Max characters of cleaned HTML sent to the selector agent (keeps prompts cheap).
MAX_HTML_CHARS_FOR_SELECTOR = control.RADAR_MAX_HTML_CHARS_FOR_SELECTOR

# Politeness delay between page fetches against the SAME source (seconds).
# Probing showed several payments outlets start returning 403 when hit back to
# back with no gap, so this is correctness, not just etiquette.
FETCH_DELAY_SECONDS = control.RADAR_FETCH_DELAY_SECONDS
