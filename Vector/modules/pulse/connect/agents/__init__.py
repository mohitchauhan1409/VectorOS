"""Connect agents — reply classification (reused from Inbox) + LinkedIn conversation."""

from modules.pulse.connect.agents.conversation_agent import ConversationAgent
# The reply classifier is channel-agnostic — reuse Inbox's directly.
from modules.pulse.inbox.agents import ReplyClassifierAgent

__all__ = ["ConversationAgent", "ReplyClassifierAgent"]
