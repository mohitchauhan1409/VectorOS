"""Base class for tools that agents can call.

Tools are small, reusable capabilities (API calls, data lookups, scrapers)
that any module's agent can invoke. Keep concrete tools in this folder.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Abstract base class for all agent tools."""

    #: Unique tool name used by agents to reference the tool.
    name: str = "base-tool"

    #: Short description of what the tool does (used in agent prompts).
    description: str = ""

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool and return its result."""
        raise NotImplementedError
