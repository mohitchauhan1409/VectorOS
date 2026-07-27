"""Base agent class shared by every GTM module.

Each module builds its own agent by subclassing `BaseAgent` and implementing
`run`. Common concerns (LLM access, logging, tool registration) live here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from modules.common.llm import Provider, get_llm
from modules.common.logger import get_logger
from modules.common.tools.base_tool import BaseTool


class BaseAgent(ABC):
    """Abstract base class for all Vector agents."""

    #: Human-readable name for the agent; override in subclasses.
    name: str = "base-agent"

    def __init__(
        self,
        provider: Provider | None = None,
        tools: list[BaseTool] | None = None,
        **llm_kwargs: Any,
    ) -> None:
        self.logger = get_logger(self.name)
        self.llm = get_llm(provider, **llm_kwargs)
        self.tools: list[BaseTool] = tools or []

    def register_tool(self, tool: BaseTool) -> None:
        """Attach a tool to this agent."""
        self.tools.append(tool)

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the agent's core task. Implemented by each module."""
        raise NotImplementedError
