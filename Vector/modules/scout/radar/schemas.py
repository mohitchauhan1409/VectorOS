"""Shared data models for Radar.

Pydantic models double as (a) the structured-output schema for the LLM agents
and (b) the shape of the lead records written to ``data/Leads``.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Selector inference (SelectorAgent output)
# ---------------------------------------------------------------------------
class ArticleSelectors(BaseModel):
    """CSS selectors that extract article listings from a news page.

    All selectors are BeautifulSoup ``.select()`` compatible. The item
    selectors are evaluated *relative to* each ``article_container`` match.
    """

    article_container: str = Field(
        description="CSS selector matching each individual article item in the list."
    )
    headline_selector: str = Field(
        description="Selector (relative to the container) for the article headline text."
    )
    link_selector: str = Field(
        description="Selector (relative to the container) for the element holding the article link."
    )
    link_attribute: str = Field(
        default="href",
        description="Attribute on the link element that holds the URL (usually 'href').",
    )
    date_selector: str | None = Field(
        default=None, description="Optional selector for the article's published date."
    )
    summary_selector: str | None = Field(
        default=None, description="Optional selector for a short article summary/excerpt."
    )
    notes: str = Field(default="", description="Any caveats about this page's structure.")


# ---------------------------------------------------------------------------
# Parsed articles
# ---------------------------------------------------------------------------
class RawArticle(BaseModel):
    """A structured article extracted from a listing page."""

    headline: str
    url: str
    published_date: str | None = None
    summary: str | None = None
    source_name: str


# ---------------------------------------------------------------------------
# Lead extraction (LeadExtractionAgent output)
# ---------------------------------------------------------------------------
class SignalType(str, Enum):
    FUNDING = "funding"
    EXPANSION = "expansion"
    HIRING = "hiring"
    PRODUCT_LAUNCH = "product_launch"
    LEADERSHIP_HIRE = "leadership_hire"
    MERGER_ACQUISITION = "merger_acquisition"
    PARTNERSHIP = "partnership"
    AWARD_RECOGNITION = "award_recognition"
    OTHER = "other"


class LeadInsight(BaseModel):
    """What the lead-extraction agent derives from a single headline/article."""

    is_lead: bool = Field(
        description="True only if a specific, targetable company is the subject of the article."
    )
    company_name: str | None = Field(
        default=None, description="The primary company the article is about."
    )
    signal_type: SignalType = Field(
        default=SignalType.OTHER, description="The kind of buying signal in the article."
    )
    reason_to_target: str | None = Field(
        default=None,
        description="One or two sentences on WHY this company is worth reaching out to now.",
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence that this is a real, targetable lead."
    )


# ---------------------------------------------------------------------------
# ICP rating (ICPRatingAgent output)
# ---------------------------------------------------------------------------
class ICPTier(str, Enum):
    A = "A"  # excellent fit
    B = "B"  # good fit
    C = "C"  # marginal fit
    D = "D"  # poor fit


class ICPRating(BaseModel):
    """How well a lead matches our Ideal Customer Profile."""

    score: int = Field(ge=0, le=100, description="Overall ICP fit score, 0-100.")
    tier: ICPTier = Field(description="A (best) to D (worst) fit tier.")
    rationale: str = Field(description="Short explanation of the score.")
    matched_criteria: list[str] = Field(
        default_factory=list, description="ICP criteria this lead clearly satisfies."
    )
    concerns: list[str] = Field(
        default_factory=list, description="Reasons for doubt or mismatch."
    )


# ---------------------------------------------------------------------------
# Enrichment + final lead record
# ---------------------------------------------------------------------------
class Enrichment(BaseModel):
    """External identifiers found for a company."""

    website_url: str | None = None
    linkedin_url: str | None = None


class Lead(BaseModel):
    """The final, persisted lead record."""

    company_name: str
    company_slug: str
    signal_type: SignalType
    reason_to_target: str | None
    confidence: float
    website_url: str | None
    linkedin_url: str | None
    icp: ICPRating
    # Quality gate: True when icp.score >= MIN_ICP_SCORE. Downstream stages
    # (e.g. Detective) only work qualified leads, to keep quality high and
    # avoid spending enrichment credits on poor-fit companies.
    qualified: bool = False
    # provenance
    source_radar: str = "news"
    source_name: str
    article_headline: str
    article_url: str
    published_date: str | None
    discovered_at: str  # ISO timestamp, stamped at save time
