"""ProfileExtractionAgent — picks decision-makers from web-search results.

Web searches for "<company> <role> linkedin" return noisy results (wrong
people, namesakes, aggregator pages). This agent reads the candidate results
and returns only the people who plausibly hold a target role AT the company,
with their name, title, and LinkedIn URL.

Runs on the NORMAL tier (cheap, fast model) — triage, not deep reasoning.
"""

from __future__ import annotations

from modules.common.base_agent import BaseAgent
from modules.scout.detective.config import NORMAL_LLM
from modules.scout.detective.schemas import DecisionMakerList

_SYSTEM = """You are a B2B research analyst identifying a company's decision-makers.

You are given a COMPANY, the target ROLES we care about, and a list of web
search results (title, url, snippet) — mostly LinkedIn profiles.

Return ONLY people who genuinely appear to hold one of the target roles AT THIS
company. For each, provide:
- name: the person's full name (clean, no titles/emojis)
- title: their role exactly as shown (e.g. "Co-Founder & CTO")
- role_category: which target role they map to (e.g. "CTO", "CEO", "Head of AI")
- linkedin_url: their linkedin.com/in/... URL from the results
- confidence: 0.0-1.0 that this is really this role at THIS company

Strict rules:
- Only use linkedin.com/in/ profile URLs that appear in the results. Never invent URLs.
- Reject namesakes at other companies, generic company pages, and article/list pages.
- If the same person appears twice, include them once.
- If no result clearly matches a role, don't fabricate one — omit it.
- Prefer current employees; lower confidence if tenure is unclear."""


class ProfileExtractionAgent(BaseAgent):
    """Extracts decision-makers (`DecisionMakerList`) from search results."""

    name = "detective-profile-agent"

    def __init__(self, **llm_kwargs) -> None:
        super().__init__(provider=NORMAL_LLM["provider"], model=NORMAL_LLM["model"], **llm_kwargs)
        self._structured = self.llm.with_structured_output(DecisionMakerList)

    def run(self, company_name: str, roles: list[str], results: list[dict]) -> DecisionMakerList:
        """Return the decision-makers found for ``company_name``.

        Args:
            company_name: The target company.
            roles: Target role names we're hunting.
            results: List of {title, url, snippet} search-result dicts.
        """
        lines = [f"- title: {r.get('title','')}\n  url: {r.get('url','')}\n  snippet: {r.get('snippet','')}"
                 for r in results]
        prompt = (
            f"{_SYSTEM}\n\n"
            f"COMPANY: {company_name}\n"
            f"TARGET ROLES: {', '.join(roles)}\n\n"
            f"SEARCH RESULTS:\n" + "\n".join(lines)
        )
        result = self._structured.invoke(prompt)
        self.logger.info("%s -> %d decision-maker(s)", company_name, len(result.people))
        return result
