"""Central configuration for the Vector GTM Engine.

Loads environment variables from a `.env` file and exposes them through a
single typed `Settings` object so modules never read `os.environ` directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Project paths (this file lives at modules/common/config.py)
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"

# Load variables from .env (if present) into the environment
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    """Runtime settings pulled from the environment."""

    # LLM provider keys
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))

    # Google Programmable Search (Custom Search JSON API) — used by GoogleSearchTool
    google_cse_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_CSE_API_KEY", ""))
    google_cse_cx: str = field(default_factory=lambda: os.getenv("GOOGLE_CSE_CX", ""))

    # Apollo.io — used by Detective for decision-maker enrichment (email etc.)
    apollo_api_key: str = field(default_factory=lambda: os.getenv("APOLLO_API_KEY", ""))

    # People Data Labs — alternative email-finding provider for Detective
    pdl_api_key: str = field(default_factory=lambda: os.getenv("PDL_API_KEY", ""))

    # Default models
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-opus-4-8"))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-pro"))

    # Which provider agents use by default: "claude" or "gemini"
    default_llm_provider: str = field(default_factory=lambda: os.getenv("DEFAULT_LLM_PROVIDER", "claude"))

    # App
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached, singleton `Settings` instance."""
    return Settings()
