"""Data models for Connect (LinkedIn outreach).

Mirrors Inbox's design; the key differences are LinkedIn-shaped:
  * a two-phase flow — a connection *invite* must be ACCEPTED before you can
    message, so acceptance is a gate in the state machine;
  * prospects are keyed by ``linkedin_url`` (+ a provider account), not email.

Channel-agnostic reply/conversation models are reused from Inbox so the
classifier + conversation agents behave identically across both channels.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

# Reuse the shared reply/conversation vocabulary (identical semantics).
from modules.pulse.inbox.schemas import (  # noqa: F401
    ConversationAction,
    ConversationDecision,
    ReplyClass,
    ReplyClassification,
)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class CampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"


class ProspectStatus(str, Enum):
    PENDING = "pending"              # enrolled, no invite sent yet
    INVITE_SENT = "invite_sent"      # connection request sent, awaiting acceptance
    ACCEPTED = "accepted"            # accepted → message sequence is active
    IN_CONVERSATION = "in_conversation"
    MEETING = "meeting"              # in scheduling — proposing/negotiating times
    BOOKED = "booked"                # meeting confirmed on the calendar
    NOT_INTERESTED = "not_interested"
    NEEDS_HUMAN = "needs_human"
    COMPLETED = "completed"          # message sequence finished, no reply
    INVITE_EXPIRED = "invite_expired"  # never accepted within the window
    UNSUBSCRIBED = "unsubscribed"
    FAILED = "failed"


class StepKind(str, Enum):
    INVITE = "invite"
    MESSAGE = "message"


class MessageKind(str, Enum):
    INVITE = "invite"
    MESSAGE = "message"


class MessageStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    REPLIED = "replied"


# ---------------------------------------------------------------------------
# Sending account
# ---------------------------------------------------------------------------
class LinkedInAccount(BaseModel):
    """A LinkedIn identity we send from (via the active provider)."""

    id: int | None = None
    name: str = ""
    provider: str = "mock"
    provider_account_id: str = ""    # id/handle the provider uses for this account
    daily_invite_cap: int = 20
    weekly_invite_cap: int = 100
    daily_message_cap: int = 40
    warmup_started_on: str | None = None
    status: AccountStatus = AccountStatus.ACTIVE
    created_at: str = Field(default_factory=utcnow_iso)


# ---------------------------------------------------------------------------
# Campaign / sequence / variants
# ---------------------------------------------------------------------------
class Variant(BaseModel):
    """A/B arm of a step (Beta posterior for the bandit — same as Inbox)."""

    id: int | None = None
    step_id: int | None = None
    name: str = ""
    angle: str = ""
    template: str = ""
    sent_count: int = 0
    reply_count: int = 0
    alpha: float = 1.0
    beta: float = 1.0
    is_winner: bool = False
    is_paused: bool = False
    created_at: str = Field(default_factory=utcnow_iso)


class SequenceStep(BaseModel):
    id: int | None = None
    campaign_id: int | None = None
    step_order: int = 1
    name: str = ""
    kind: StepKind = StepKind.MESSAGE
    angle: str = ""
    wait_days: int = 0
    variants: list[Variant] = Field(default_factory=list)


class Campaign(BaseModel):
    id: int | None = None
    name: str
    description: str = ""
    status: CampaignStatus = CampaignStatus.DRAFT
    icp_min_score: int = 0
    created_at: str = Field(default_factory=utcnow_iso)
    steps: list[SequenceStep] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Prospect (enrollment)
# ---------------------------------------------------------------------------
class Prospect(BaseModel):
    """A decision-maker enrolled into a LinkedIn campaign."""

    id: int | None = None
    campaign_id: int | None = None

    lead_slug: str = ""
    company: str = ""
    name: str = ""
    title: str = ""
    role_category: str = ""
    linkedin_url: str = ""
    email: str = ""                      # from Detective (for calendar invites)

    status: ProspectStatus = ProspectStatus.PENDING
    current_step: int = 0
    account_id: int | None = None        # sticky sending account
    next_action_at: str | None = None
    invited_at: str | None = None
    accepted_at: str | None = None
    last_action_at: str | None = None
    replied_at: str | None = None
    enrolled_at: str = Field(default_factory=utcnow_iso)

    context: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Outbound message / inbound reply
# ---------------------------------------------------------------------------
class ConnectDraft(BaseModel):
    """Composed but unsent note/message."""

    body: str
    variant_id: int | None = None


class ConnectMessage(BaseModel):
    id: int | None = None
    prospect_id: int | None = None
    campaign_id: int | None = None
    step_id: int | None = None
    variant_id: int | None = None
    account_id: int | None = None

    kind: MessageKind = MessageKind.MESSAGE
    body: str = ""
    provider_ref: str = ""           # provider's id for the sent action (container/chat/etc.)
    status: MessageStatus = MessageStatus.QUEUED
    error: str = ""
    queued_at: str = Field(default_factory=utcnow_iso)
    sent_at: str | None = None


class Reply(BaseModel):
    id: int | None = None
    prospect_id: int | None = None
    body: str = ""
    received_at: str = Field(default_factory=utcnow_iso)
    provider_id: str = ""            # dedupe key from the provider
    classification: ReplyClass = ReplyClass.OTHER
    classification_confidence: float = 0.0
    resume_at: str | None = None


# ---------------------------------------------------------------------------
# Provider result objects
# ---------------------------------------------------------------------------
class ActionResult(BaseModel):
    """Uniform result of a provider send (invite or message)."""

    ok: bool = False
    provider_ref: str = ""
    error: str = ""


class InboundMessage(BaseModel):
    """A raw inbound message a provider surfaces (pre-matching)."""

    linkedin_url: str = ""
    provider_id: str = ""
    text: str = ""
    received_at: str = Field(default_factory=utcnow_iso)
