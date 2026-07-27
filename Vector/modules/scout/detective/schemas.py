"""Data models for Detective."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DecisionMaker(BaseModel):
    """A decision-maker found for a company.

    Populated in two stages: the profile-extraction agent fills identity fields
    from web search; Apollo (optional) fills contact fields.
    """

    # From web search + agent
    name: str = Field(description="Full name of the person.")
    title: str = Field(default="", description="Their role/title as stated online.")
    role_category: str = Field(
        default="", description="Which target role this person maps to (e.g. 'CTO')."
    )
    linkedin_url: str = Field(default="", description="LinkedIn profile URL (linkedin.com/in/...).")
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Confidence that this person really holds this role at the company.",
    )

    # From email enrichment (filled later; None until enriched)
    email: str | None = None
    email_status: str | None = None       # e.g. "verified", "guessed", "unverified"
    email_source: str | None = None       # which provider found it: pdl/apollo/pattern
    apollo_id: str | None = None
    city: str | None = None
    country: str | None = None
    enriched: bool = False


class DecisionMakerList(BaseModel):
    """Structured-output wrapper: the people the agent selected for a company."""

    people: list[DecisionMaker] = Field(default_factory=list)
