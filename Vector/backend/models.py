"""SQLAlchemy ORM models — the unified Vector schema.

Design goals:
  * Fully normalized (no JSON blobs) so every field is queryable/indexable.
  * Everything scoped to a workspace so the demo account and real accounts
    are fully isolated in one DB.
  * Mirrors the engine's domain: Scout -> Company/Signal/Person,
    Pulse -> Campaign/Sequence/Step/Variant/Enrollment/Message,
    plus Event (timeline) and PipelineRun (engine run tracking).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Workspace / User
# --------------------------------------------------------------------------- #

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    users: Mapped[list["User"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(100), default="Member")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    workspace: Mapped[Workspace] = relationship(back_populates="users")


# --------------------------------------------------------------------------- #
# Scout — Companies, Signals, People
# --------------------------------------------------------------------------- #

class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_company_slug"),
        Index("ix_companies_ws", "workspace_id"),
        Index("ix_companies_ws_score", "workspace_id", "icp_score"),
        Index("ix_companies_ws_signal", "workspace_id", "signal_type"),
        Index("ix_companies_ws_tier", "workspace_id", "icp_tier"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255))
    website_url: Mapped[str | None] = mapped_column(String(500))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    industry: Mapped[str] = mapped_column(String(200), default="")
    employee_range: Mapped[str] = mapped_column(String(50), default="")
    location: Mapped[str] = mapped_column(String(200), default="")

    signal_type: Mapped[str] = mapped_column(String(50), default="other")
    reason_to_target: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # FIT and INTENT are deliberately separate numbers. Fit is structural and
    # stable (does this company carry merchant credit risk it could transfer to
    # us). Intent is timing and it decays (has something moved recently). One
    # blended score hides the difference an SDR most needs: "great account, no
    # reason to call today" vs "average account, call this week".
    icp_score: Mapped[int] = mapped_column(Integer, default=0)   # = fit
    icp_tier: Mapped[str] = mapped_column(String(1), default="D")
    intent_score: Mapped[int] = mapped_column(Integer, default=0)
    signal_age_days: Mapped[int] = mapped_column(Integer, default=0)
    icp_rationale: Mapped[str] = mapped_column(Text, default="")
    qualified: Mapped[bool] = mapped_column(Boolean, default=False)

    source_radar: Mapped[str] = mapped_column(String(50), default="news")
    source_name: Mapped[str] = mapped_column(String(255), default="")
    article_headline: Mapped[str] = mapped_column(Text, default="")
    article_url: Mapped[str] = mapped_column(String(500), default="")
    published_date: Mapped[str | None] = mapped_column(String(50))
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    criteria: Mapped[list["ICPCriterion"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    signals: Mapped[list["Signal"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", order_by="Signal.discovered_at.desc()"
    )
    people: Mapped[list["Person"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class Sponsorship(Base):
    """A sponsor bank -> sponsored payfac/PSP edge.

    Modelled explicitly because it changes who you should be talking to: if the
    sponsor sets the collateral formula, the deal is upstream of the payfac. One
    sponsor relationship also unlocks every entity on its book.
    """

    __tablename__ = "sponsorships"
    __table_args__ = (
        UniqueConstraint("sponsor_id", "sponsored_id", name="uq_sponsorship"),
        Index("ix_sponsorships_sponsor", "sponsor_id"),
        Index("ix_sponsorships_sponsored", "sponsored_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    sponsor_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    sponsored_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))


class ICPCriterion(Base):
    __tablename__ = "icp_criteria"
    __table_args__ = (Index("ix_criteria_company", "company_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # 'matched' | 'concern'
    text: Mapped[str] = mapped_column(Text)

    company: Mapped[Company] = relationship(back_populates="criteria")


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (Index("ix_signals_company", "company_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    signal_type: Mapped[str] = mapped_column(String(50))
    reason_to_target: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    article_headline: Mapped[str] = mapped_column(Text, default="")
    article_url: Mapped[str] = mapped_column(String(500), default="")
    published_date: Mapped[str | None] = mapped_column(String(50))
    source_name: Mapped[str] = mapped_column(String(255), default="")
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    company: Mapped[Company] = relationship(back_populates="signals")


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (
        Index("ix_people_ws", "workspace_id"),
        Index("ix_people_company", "company_id"),
        Index("ix_people_ws_role", "workspace_id", "role_category"),
        Index("ix_people_ws_email_status", "workspace_id", "email_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255), default="")
    role_category: Mapped[str] = mapped_column(String(100), default="")
    linkedin_url: Mapped[str] = mapped_column(String(500), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    email: Mapped[str | None] = mapped_column(String(320))
    email_status: Mapped[str | None] = mapped_column(String(20))  # verified|guessed|unverified
    email_source: Mapped[str | None] = mapped_column(String(50))
    apollo_id: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(120))
    enriched: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    company: Mapped[Company] = relationship(back_populates="people")


# --------------------------------------------------------------------------- #
# Pulse — Campaign > Sequence(email|linkedin) > Step > Variant
# --------------------------------------------------------------------------- #

# How the first touch leaves the building.
#   manual     — nothing goes out until a human releases each person (default)
#   autonomous — the engine sends the first touch as soon as it's due
SEND_MODES = ("manual", "autonomous")


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (Index("ix_campaigns_ws", "workspace_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    #: Defaults to manual on purpose — a new campaign should never start
    #: emailing real people until someone deliberately releases it.
    send_mode: Mapped[str] = mapped_column(String(20), default="manual")
    icp_min_score: Mapped[int] = mapped_column(Integer, default=35)
    theme: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    sequences: Mapped[list["Sequence"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class Sequence(Base):
    __tablename__ = "sequences"
    __table_args__ = (
        UniqueConstraint("campaign_id", "channel", name="uq_sequence_channel"),
        Index("ix_sequences_campaign", "campaign_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(20))  # 'email' | 'linkedin'
    name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    campaign: Mapped[Campaign] = relationship(back_populates="sequences")
    steps: Mapped[list["SequenceStep"]] = relationship(
        back_populates="sequence", cascade="all, delete-orphan", order_by="SequenceStep.step_order"
    )


class SequenceStep(Base):
    __tablename__ = "sequence_steps"
    __table_args__ = (Index("ix_steps_sequence", "sequence_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sequence_id: Mapped[int] = mapped_column(ForeignKey("sequences.id", ondelete="CASCADE"))
    step_order: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    angle: Mapped[str] = mapped_column(Text, default="")
    wait_days: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str | None] = mapped_column(String(20))  # linkedin: invite|message

    sequence: Mapped[Sequence] = relationship(back_populates="steps")
    variants: Mapped[list["Variant"]] = relationship(
        back_populates="step", cascade="all, delete-orphan", order_by="Variant.id"
    )


class Variant(Base):
    __tablename__ = "variants"
    __table_args__ = (Index("ix_variants_step", "step_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    step_id: Mapped[int] = mapped_column(ForeignKey("sequence_steps.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    angle: Mapped[str] = mapped_column(Text, default="")
    subject_template: Mapped[str | None] = mapped_column(Text)  # null for linkedin
    body_template: Mapped[str] = mapped_column(Text, default="")
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    alpha: Mapped[float] = mapped_column(Float, default=1.0)
    beta: Mapped[float] = mapped_column(Float, default=1.0)
    is_winner: Mapped[bool] = mapped_column(Boolean, default=False)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    step: Mapped[SequenceStep] = relationship(back_populates="variants")


# --------------------------------------------------------------------------- #
# Enrollments / Messages / Timeline / Runs
# --------------------------------------------------------------------------- #

class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        Index("ix_enroll_ws", "workspace_id"),
        Index("ix_enroll_campaign", "campaign_id"),
        Index("ix_enroll_sequence", "sequence_id"),
        Index("ix_enroll_person", "person_id"),
        Index("ix_enroll_status", "workspace_id", "status"),
        UniqueConstraint("sequence_id", "person_id", name="uq_enroll_seq_person"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    sequence_id: Mapped[int] = mapped_column(ForeignKey("sequences.id", ondelete="CASCADE"))
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(20))
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="active")
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_action_at: Mapped[datetime | None] = mapped_column(DateTime)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    needs_human_reason: Mapped[str | None] = mapped_column(String(60))

    #: When a human released this person's first touch. Only meaningful while the
    #: campaign is in manual mode; once the sequence is underway it stops
    #: mattering. Deliberately preserved across pulse_sync rebuilds — it records
    #: a human decision the engine stores know nothing about.
    launched_at: Mapped[datetime | None] = mapped_column(DateTime)
    launched_by: Mapped[str | None] = mapped_column(String(200))


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_person", "person_id"),
        Index("ix_messages_enrollment", "enrollment_id"),
        Index("ix_messages_ws", "workspace_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    enrollment_id: Mapped[int | None] = mapped_column(ForeignKey("enrollments.id", ondelete="CASCADE"))
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"))
    sequence_id: Mapped[int | None] = mapped_column(ForeignKey("sequences.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(String(20))
    direction: Mapped[str] = mapped_column(String(10))  # outbound | inbound
    step_name: Mapped[str] = mapped_column(String(255), default="")
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str | None] = mapped_column(String(20))
    reply_class: Mapped[str | None] = mapped_column(String(30))
    at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_ws", "workspace_id"),
        Index("ix_events_person", "person_id"),
        Index("ix_events_ws_created", "workspace_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(50))
    channel: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Mailbox(Base):
    """Synced from the engine's inbox mailbox pool — shows sending capacity/warmup."""

    __tablename__ = "mailboxes"
    __table_args__ = (
        UniqueConstraint("workspace_id", "email", name="uq_mailbox_email"),
        Index("ix_mailboxes_ws", "workspace_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(320))
    from_name: Mapped[str] = mapped_column(String(200), default="")
    provider: Mapped[str] = mapped_column(String(50), default="")
    daily_cap: Mapped[int] = mapped_column(Integer, default=40)
    daily_allowance: Mapped[int] = mapped_column(Integer, default=10)  # today's ramped cap
    sent_today: Mapped[int] = mapped_column(Integer, default=0)
    warmup_started_on: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="active")


class LinkedInAccount(Base):
    """Synced from the engine's connect account — shows invite/message capacity."""

    __tablename__ = "linkedin_accounts"
    __table_args__ = (Index("ix_liaccounts_ws", "workspace_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200), default="")
    provider: Mapped[str] = mapped_column(String(50), default="mock")
    daily_invite_cap: Mapped[int] = mapped_column(Integer, default=20)
    weekly_invite_cap: Mapped[int] = mapped_column(Integer, default=100)
    daily_message_cap: Mapped[int] = mapped_column(Integer, default=40)
    invite_allowance: Mapped[int] = mapped_column(Integer, default=5)
    invites_today: Mapped[int] = mapped_column(Integer, default=0)
    invites_week: Mapped[int] = mapped_column(Integer, default=0)
    messages_today: Mapped[int] = mapped_column(Integer, default=0)
    warmup_started_on: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="active")


class Meeting(Base):
    """A booked (or proposed) meeting, from the scheduling flow."""

    __tablename__ = "meetings"
    __table_args__ = (
        Index("ix_meetings_ws", "workspace_id"),
        Index("ix_meetings_person", "person_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(String(20), default="email")
    status: Mapped[str] = mapped_column(String(20), default="booked")  # booked|proposed|cancelled
    slot_start: Mapped[str | None] = mapped_column(String(40))
    join_url: Mapped[str | None] = mapped_column(String(500))
    event_id: Mapped[str | None] = mapped_column(String(200))
    attendee_email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# --------------------------------------------------------------------------- #
# Closer — Deals (post-first-meeting pipeline)
#
# A Deal opens once the intro call has actually happened and the conversation
# moves to "what would it take to close this". The Closer module (in dev) will
# populate these from meeting transcripts/notes; until then the demo workspace
# is seeded with representative data so the UI is exercised end-to-end.
# --------------------------------------------------------------------------- #

# Ordered — index is the progress position shown in the UI.
DEAL_STAGES = ("discovery", "evaluation", "proposal", "negotiation", "closed_won", "closed_lost")
OPEN_DEAL_STAGES = ("discovery", "evaluation", "proposal", "negotiation")


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        UniqueConstraint("person_id", name="uq_deal_person"),
        Index("ix_deals_ws", "workspace_id"),
        Index("ix_deals_company", "company_id"),
        Index("ix_deals_ws_stage", "workspace_id", "stage"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"))

    stage: Mapped[str] = mapped_column(String(20), default="discovery")
    health: Mapped[str] = mapped_column(String(20), default="on_track")  # on_track|at_risk|stalled
    probability: Mapped[int] = mapped_column(Integer, default=0)         # 0-100
    value_usd: Mapped[int] = mapped_column(Integer, default=0)           # annual contract value
    owner: Mapped[str] = mapped_column(String(120), default="")
    source_channel: Mapped[str] = mapped_column(String(20), default="email")

    #: AI-written executive summary of where the deal stands.
    summary: Mapped[str] = mapped_column(Text, default="")
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    expected_close: Mapped[str | None] = mapped_column(String(20))       # ISO date
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    meetings: Mapped[list["ContactMeeting"]] = relationship(
        back_populates="deal", order_by="ContactMeeting.occurred_at.desc()",
    )
    next_steps: Mapped[list["DealNextStep"]] = relationship(
        back_populates="deal", cascade="all, delete-orphan",
        order_by="DealNextStep.step_order",
    )
    highlights: Mapped[list["DealHighlight"]] = relationship(
        back_populates="deal", cascade="all, delete-orphan", order_by="DealHighlight.id",
    )


# Meetings hang off the PERSON, not the deal: a first meeting has to happen
# before a deal exists, and plenty of meetings never become one. `deal_id` is a
# back-reference that gets set once a deal opens.
MEETING_STATUSES = ("scheduled", "completed", "cancelled")


class ContactMeeting(Base):
    """A meeting with a contact — upcoming, held, or cancelled."""

    __tablename__ = "contact_meetings"
    __table_args__ = (
        # Index names are global in SQLite — keep them table-prefixed so they
        # can't collide with the scheduling-flow `meetings` table below.
        Index("ix_contact_meetings_ws", "workspace_id"),
        Index("ix_contact_meetings_person", "person_id"),
        Index("ix_contact_meetings_deal", "deal_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"))

    title: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(30), default="discovery")  # discovery|demo|technical|pricing|exec|intro
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    duration_min: Mapped[int] = mapped_column(Integer, default=30)
    attendees: Mapped[str] = mapped_column(Text, default="")            # comma-separated
    location: Mapped[str] = mapped_column(String(500), default="")      # meet link / room
    sentiment: Mapped[str] = mapped_column(String(20), default="neutral")  # positive|neutral|negative

    #: Raw notes a human typed in. Closer turns these into `summary` + points.
    notes: Mapped[str] = mapped_column(Text, default="")
    #: AI-written recap. Empty until Closer has processed the meeting.
    summary: Mapped[str] = mapped_column(Text, default="")
    #: Where the transcript came from — mirrors the Closer PLAN's tiers.
    source: Mapped[str] = mapped_column(String(30), default="manual")
    recording_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    deal: Mapped[Deal | None] = relationship(back_populates="meetings")
    points: Mapped[list["MeetingPoint"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", order_by="MeetingPoint.id",
    )


class MeetingPoint(Base):
    """A single extracted line from a meeting — takeaway / objection / question / commitment."""

    __tablename__ = "meeting_points"
    __table_args__ = (Index("ix_meeting_points_meeting", "meeting_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("contact_meetings.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # takeaway|objection|question|commitment
    text: Mapped[str] = mapped_column(Text)

    meeting: Mapped[ContactMeeting] = relationship(back_populates="points")


class DealNextStep(Base):
    """The recommended next action to move the deal toward close."""

    __tablename__ = "deal_next_steps"
    __table_args__ = (Index("ix_deal_steps_deal", "deal_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    step_order: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(120), default="")
    due_date: Mapped[str | None] = mapped_column(String(20))            # ISO date
    priority: Mapped[str] = mapped_column(String(10), default="medium")  # high|medium|low
    status: Mapped[str] = mapped_column(String(15), default="todo")      # todo|done|blocked
    #: Which meeting this recommendation was derived from (for "why am I seeing this").
    rationale: Mapped[str] = mapped_column(Text, default="")

    deal: Mapped[Deal] = relationship(back_populates="next_steps")


class DealHighlight(Base):
    """A key signal the analysis surfaced — what's working, what could kill the deal."""

    __tablename__ = "deal_highlights"
    __table_args__ = (Index("ix_deal_highlights_deal", "deal_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # strength|risk|blocker|signal
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    deal: Mapped[Deal] = relationship(back_populates="highlights")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (Index("ix_runs_ws", "workspace_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|succeeded|failed
    stage: Mapped[str] = mapped_column(String(50), default="queued")
    mode: Mapped[str] = mapped_column(String(20), default="live")
    companies_found: Mapped[int] = mapped_column(Integer, default=0)
    people_found: Mapped[int] = mapped_column(Integer, default=0)
    enrolled: Mapped[int] = mapped_column(Integer, default=0)
    messages_sent: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
