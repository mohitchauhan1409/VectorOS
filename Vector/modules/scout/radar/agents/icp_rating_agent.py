"""ICPRatingAgent — scores a lead against our Ideal Customer Profile.

Reads our company/ICP profile from config and rates how well a discovered lead
fits, producing a 0-100 score, an A-D tier, and a short rationale. This is the
gate that keeps only high-quality leads.

Runs on the HIGH_EFFORT tier (a high-intelligence model) — qualification is the
most reasoning-heavy step and the most defensible place to spend those tokens.
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.scout.radar.config import COMPANY_PROFILE, HIGH_EFFORT_LLM
from modules.scout.radar.schemas import Enrichment, ICPRating, LeadInsight

_SYSTEM = """You are a sales-qualification expert.
Given OUR company/ICP profile and a discovered lead, rate how well the lead fits
our Ideal Customer Profile.

Return:
- score: 0-100 overall fit (100 = perfect fit and perfect timing).
- tier: A (excellent), B (good), C (marginal), D (poor).
- rationale: 1-2 sentences justifying the score.
- matched_criteria: specific ICP criteria the lead clearly satisfies.
- concerns: mismatches, disqualifiers, or unknowns lowering confidence.

Weigh BOTH fit (industry, size, geography, persona) AND timing (the buying signal).
Apply disqualifiers strictly — a disqualified company should score low (tier D)."""


class ICPRatingAgent(BaseAgent):
    """Rates a `LeadInsight` against `COMPANY_PROFILE`, returning an `ICPRating`."""

    name = "radar-icp-rating-agent"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=HIGH_EFFORT_LLM["provider"], model=HIGH_EFFORT_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(ICPRating)

    def run(self, insight: LeadInsight, enrichment: Enrichment | None = None) -> ICPRating:
        """Return the ICP rating for a lead."""
        enrichment = enrichment or Enrichment()
        prompt = (
            f"{_SYSTEM}\n\n"
            f"--- OUR ICP ---\n{COMPANY_PROFILE.as_prompt()}\n\n"
            f"--- THE LEAD ---\n"
            f"COMPANY: {insight.company_name}\n"
            f"SIGNAL: {insight.signal_type.value}\n"
            f"WHY NOW: {insight.reason_to_target}\n"
            f"WEBSITE: {enrichment.website_url or '(unknown)'}\n"
            f"LINKEDIN: {enrichment.linkedin_url or '(unknown)'}"
        )
        rating = self._structured.invoke(prompt)
        self.logger.info(
            "ICP rating for %s: score=%d tier=%s",
            insight.company_name, rating.score, rating.tier,
        )
        return rating
