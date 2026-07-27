"""Data models for Inbox (PULSE module).

These Pydantic models are the in-memory domain objects. ``store.py`` maps them
to/from SQLite rows. Enums are plain ``str`` subclasses so they serialize
cleanly to the DB and to JSON without adapters.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utcnow_iso() -> str:
    """Timezone-aware UTC timestamp as an ISO string (how we store all times)."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class CampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"        # retired by the experiment's weekly evolution


class RecipientStatus(str, Enum):
    ACTIVE = "active"                  # in-sequence, eligible for the next step
    REPLIED = "replied"                # got a reply (transient; handler re-routes)
    IN_CONVERSATION = "in_conversation"  # agent is handling a live back-and-forth
    MEETING = "meeting"                # in scheduling — proposing/negotiating times
    BOOKED = "booked"                  # meeting confirmed on the calendar
    NOT_INTERESTED = "not_interested"  # gracefully closed lost
    NEEDS_HUMAN = "needs_human"        # escalated — a person should step in
    BOUNCED = "bounced"                # hard bounce → stop
    UNSUBSCRIBED = "unsubscribed"
    COMPLETED = "completed"            # finished all steps, no reply
    PAUSED = "paused"


class MessageStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"
    OPENED = "opened"
    REPLIED = "replied"


class ReplyClass(str, Enum):
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    OBJECTION = "objection"
    REFERRAL = "referral"          # "talk to <someone else>"
    OUT_OF_OFFICE = "out_of_office"
    UNSUBSCRIBE = "unsubscribe"
    AUTO_REPLY = "auto_reply"
    OTHER = "other"


class MailboxStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"


# ---------------------------------------------------------------------------
# Mailbox
# ---------------------------------------------------------------------------
class Mailbox(BaseModel):
    """A sending/receiving account in the pool.

    The password is NEVER persisted. ``secret_ref`` names the env var that
    holds it; the sender resolves it at send time. For an ad-hoc mailbox the
    password may be held transiently on the instance via ``password`` but it is
    excluded from anything written to the store.
    """

    id: int | None = None
    email: str
    from_name: str = ""
    provider: str = ""
    smtp_host: str = ""
    smtp_port: int = 465
    imap_host: str = ""
    imap_port: int = 993
    secret_ref: str = ""              # env var name holding the password
    daily_cap: int = 40
    warmup_started_on: str | None = None   # date (YYYY-MM-DD) of first send
    status: MailboxStatus = MailboxStatus.ACTIVE
    created_at: str = Field(default_factory=utcnow_iso)

    # Transient — not written to the DB (see store.save_mailbox).
    password: str = ""


# ---------------------------------------------------------------------------
# Campaign / sequence / variants
# ---------------------------------------------------------------------------
class Variant(BaseModel):
    """One A/B arm of a sequence step.

    Bandit state lives here: each variant is a Beta(alpha, beta) posterior over
    "reply / no-reply". ``sent_count``/``reply_count`` are the observed data;
    alpha/beta are prior + successes / prior + failures maintained by the store.
    """

    id: int | None = None
    step_id: int | None = None
    name: str = ""
    angle: str = ""
    subject_template: str = ""
    body_template: str = ""
    sent_count: int = 0
    reply_count: int = 0
    alpha: float = 1.0
    beta: float = 1.0
    is_winner: bool = False
    is_paused: bool = False
    created_at: str = Field(default_factory=utcnow_iso)


class SequenceStep(BaseModel):
    """One step in a campaign's sequence (may carry several A/B variants)."""

    id: int | None = None
    campaign_id: int | None = None
    step_order: int = 1
    name: str = ""
    angle: str = ""
    wait_days: int = 0                # delay after the previous step / enrollment
    variants: list[Variant] = Field(default_factory=list)


class Campaign(BaseModel):
    """A named outreach effort: an ICP filter + a sequence of steps.

    When part of an experiment, ``group_id`` links it to its competing siblings,
    ``theme`` names its sequence strategy, and ``priority`` is its current rank
    (0 = best) used for performance-weighted lead allocation.
    """

    id: int | None = None
    name: str
    description: str = ""
    status: CampaignStatus = CampaignStatus.DRAFT
    icp_min_score: int = 0            # only enroll leads at/above this ICP score
    created_at: str = Field(default_factory=utcnow_iso)
    steps: list[SequenceStep] = Field(default_factory=list)

    # Experiment linkage (null when the campaign runs standalone).
    group_id: int | None = None
    theme: str = ""
    priority: int = 0


class CampaignGroup(BaseModel):
    """An A/B experiment: several campaigns (distinct sequences) competing for
    the same lead pool, with performance-weighted allocation + weekly evolution."""

    id: int | None = None
    name: str
    status: str = "active"
    size: int = 4                     # target number of live competing campaigns
    created_at: str = Field(default_factory=utcnow_iso)


# ---------------------------------------------------------------------------
# Recipient (enrollment) — a decision-maker enrolled into a campaign
# ---------------------------------------------------------------------------
class Recipient(BaseModel):
    """A single person enrolled into a campaign.

    ``context`` snapshots the lead signal at enrollment time so personalization
    is reproducible even if the source lead JSON later changes.
    """

    id: int | None = None
    campaign_id: int | None = None

    # Who + where they came from (denormalized from the Scout lead JSON).
    lead_slug: str = ""
    company: str = ""
    name: str = ""
    email: str = ""
    title: str = ""
    role_category: str = ""
    email_status: str = ""            # verified / guessed / unverified

    # Sequence progress.
    current_step: int = 0             # 0 = not started; N = last step sent
    status: RecipientStatus = RecipientStatus.ACTIVE
    mailbox_id: int | None = None     # sticky mailbox for the whole thread
    next_send_at: str | None = None   # when the next step is due
    last_sent_at: str | None = None
    replied_at: str | None = None
    enrolled_at: str = Field(default_factory=utcnow_iso)

    # Personalization context (lead signal snapshot), stored as JSON.
    context: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Message (outbound) & Reply (inbound)
# ---------------------------------------------------------------------------
class EmailDraft(BaseModel):
    """A composed but not-yet-sent email (Writer/AB output)."""

    subject: str
    body: str
    variant_id: int | None = None


class Message(BaseModel):
    """An outbound email and its lifecycle state."""

    id: int | None = None
    recipient_id: int | None = None
    campaign_id: int | None = None
    step_id: int | None = None
    variant_id: int | None = None
    mailbox_id: int | None = None

    to_email: str = ""
    from_email: str = ""
    subject: str = ""
    body: str = ""

    # Threading — RFC 5322 headers, so follow-ups thread and replies match back.
    rfc_message_id: str = ""          # the Message-ID we set on the outbound mail
    thread_id: str = ""               # our own stable thread token (== first msg id)
    in_reply_to: str = ""             # parent Message-ID for follow-ups

    status: MessageStatus = MessageStatus.QUEUED
    error: str = ""
    queued_at: str = Field(default_factory=utcnow_iso)
    sent_at: str | None = None
    opened_at: str | None = None


class Reply(BaseModel):
    """An inbound reply matched to one of our outbound messages."""

    id: int | None = None
    recipient_id: int | None = None
    message_id: int | None = None     # FK to the outbound Message it replies to
    from_email: str = ""
    subject: str = ""
    body: str = ""
    received_at: str = Field(default_factory=utcnow_iso)
    imap_uid: str = ""                # dedupe key (mailbox UID)
    classification: ReplyClass = ReplyClass.OTHER
    classification_confidence: float = 0.0
    resume_at: str | None = None      # for OOO: when to resume the sequence


# ---------------------------------------------------------------------------
# Structured-output wrappers for LLM agents
# ---------------------------------------------------------------------------
class ReplyClassification(BaseModel):
    """Structured output of the reply-classifier agent."""

    classification: ReplyClass
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reasoning: str = ""
    resume_date: str | None = Field(
        default=None, description="For out_of_office, the ISO date to resume (if stated)."
    )


class VariantSet(BaseModel):
    """Structured output of the A/B optimizer: several email variants."""

    variants: list[EmailDraft] = Field(default_factory=list)


class ConversationAction(str, Enum):
    """What the autonomous reply-handler decides to do with a reply."""

    ASK_AVAILABILITY = "ask_availability"    # they'll talk → propose/ask for times
    SHARE_BOOKING = "share_booking"          # share the booking link
    ANSWER_QUESTION = "answer_question"      # answer + nudge toward a meeting
    HANDLE_OBJECTION = "handle_objection"    # address concern + nudge
    POLITE_CLOSE = "polite_close"            # not interested → thank + close
    ACK_REFERRAL = "acknowledge_referral"    # thank + ask for the intro
    ESCALATE = "escalate"                    # hand to a human, don't auto-send
    IGNORE = "ignore"                        # auto-reply/OOO → do nothing


class ConversationDecision(BaseModel):
    """Structured output of the ConversationAgent: what to do + the drafted reply."""

    action: ConversationAction
    should_send: bool = Field(
        default=False, description="True only if we should auto-send the drafted reply now.")
    new_status: RecipientStatus = Field(
        default=RecipientStatus.IN_CONVERSATION,
        description="Recipient status to set after handling this reply.")
    reply_subject: str = ""
    reply_body: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reasoning: str = ""


class VariantSpec(BaseModel):
    """One A/B arm the optimizer proposes for a step: a distinct persuasion
    angle (plus an optional subject-line style hint). The Writer personalizes
    the actual copy per recipient using this angle, so arms test *strategy*,
    not a single frozen email."""

    name: str = Field(description="Short arm label, e.g. 'pain-led', 'roi', 'curiosity'.")
    angle: str = Field(description="The persuasion strategy/instruction for this arm.")
    subject_hint: str = Field(default="", description="Optional subject-line style guidance.")


class VariantSpecSet(BaseModel):
    """Structured output of the A/B optimizer agent."""

    variants: list[VariantSpec] = Field(default_factory=list)


class StepSpec(BaseModel):
    """One step of a designed sequence."""

    name: str = Field(description="Short step label, e.g. 'Intro', 'Value nudge'.")
    angle: str = Field(description="The persuasion angle/instruction for this step.")
    wait_days: int = Field(default=3, description="Days to wait after the previous step.")


class SequenceDesign(BaseModel):
    """Structured output of the sequence designer: a themed multi-step sequence."""

    theme: str = ""
    steps: list[StepSpec] = Field(default_factory=list)
