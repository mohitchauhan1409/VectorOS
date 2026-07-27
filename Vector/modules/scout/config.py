"""SCOUT-level configuration (orchestrates Radar + Detective)."""

from __future__ import annotations

# How many QUALIFIED leads (ICP >= MIN_ICP_SCORE) to generate per run. SCOUT
# keeps scanning until it collects this many, then runs Detective on each
# (decision-makers + emails). Override at the CLI:  python -m modules.scout 5
LEADS_LIMIT = 2

# Radar paginates each source up to MAX_PAGES (radar/config.py, default 50),
# finishing one source before moving to the next, and stops as soon as
# LEADS_LIMIT qualified leads are found. Lower MAX_PAGES to bound cost/time.
