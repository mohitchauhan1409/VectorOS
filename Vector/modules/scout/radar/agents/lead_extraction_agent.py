"""LeadExtractionAgent — turns an article into a lead signal.

From a headline (plus summary if available) it identifies the primary company,
classifies the buying signal, and writes a short note on why the company is
worth reaching out to now. Non-company / macro headlines are rejected.

Runs on the NORMAL tier (cheap, fast model) — high-volume triage work.
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.scout.radar.config import NORMAL_LLM
from modules.scout.radar.schemas import LeadInsight, RawArticle

_SYSTEM = """You are a B2B sales-intelligence analyst.
You read a news article headline (and summary, if given) and extract a sales lead.

Return:
- is_lead: TRUE only if the article is about a SPECIFIC, NAMEABLE company that could
  be a sales prospect. Set FALSE for macro/market news, opinion pieces, listicles,
  government-only news, or articles with no clear single company.
- company_name: the primary company the article is about (clean legal-ish name, no
  ticker symbols or extra words). Null if is_lead is false.
- signal_type: the buying signal — one of funding, expansion, hiring, product_launch,
  leadership_hire, merger_acquisition, partnership, award_recognition, other.
- reason_to_target: 1-2 crisp sentences a salesperson could act on, explaining WHY
  now is a good time to reach out (e.g. "Just raised a $20M Series A to expand its
  sales team — strong timing for GTM tooling").
- confidence: 0.0-1.0 that this is a real, targetable lead.

Be strict: a vague headline with no clear company is NOT a lead."""


class LeadExtractionAgent(BaseAgent):
    """Extracts a `LeadInsight` from a `RawArticle`."""

    name = "radar-lead-extraction-agent"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=NORMAL_LLM["provider"], model=NORMAL_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(LeadInsight)

    def run(self, article: RawArticle) -> LeadInsight:
        """Return the lead insight derived from ``article``."""
        prompt = (
            f"{_SYSTEM}\n\n"
            f"HEADLINE: {article.headline}\n"
            f"SUMMARY: {article.summary or '(none)'}\n"
            f"SOURCE: {article.source_name}"
        )
        insight = self._structured.invoke(prompt)
        self.logger.info(
            "Article -> lead=%s company=%s signal=%s",
            insight.is_lead, insight.company_name, insight.signal_type,
        )
        return insight
