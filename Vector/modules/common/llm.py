"""LLM provider factory.

Wraps LangChain chat models so every module gets its LLM from one place.
Supported providers: Anthropic Claude and Google Gemini.
"""

from __future__ import annotations

from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

from modules.common.config import get_settings

Provider = Literal["claude", "gemini"]


def get_llm(
    provider: Provider | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    **kwargs,
):
    """Return a configured LangChain chat model.

    Args:
        provider: "claude" or "gemini". Falls back to the configured default.
        model: Explicit model id. Overrides the provider's configured default —
               lets callers pick a cheap "normal" model or a high-effort one.
        temperature: Sampling temperature. Omitted from the request when None
               (some models, e.g. Opus 4.8, reject the ``temperature`` param).
        **kwargs: Extra keyword args passed to the underlying chat model.
    """
    settings = get_settings()
    provider = provider or settings.default_llm_provider  # type: ignore[assignment]

    if temperature is not None:
        kwargs["temperature"] = temperature

    if provider == "claude":
        return ChatAnthropic(
            model=model or settings.claude_model,
            api_key=settings.anthropic_api_key,
            **kwargs,
        )

    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model or settings.gemini_model,
            google_api_key=settings.google_api_key,
            **kwargs,
        )

    raise ValueError(f"Unknown LLM provider: {provider!r}. Use 'claude' or 'gemini'.")
