// Domain types — mirror the Vector backend API shapes 1:1.
// See the API contract: companies, people, campaigns (with sequences),
// enrollments, events, messages, dashboard/analytics stats, pipeline runs.

// ---------- Auth ----------

export interface User {
  id: number
  email: string
  name: string
  role: string
  is_demo: boolean
  workspace_id: number
}

export interface AuthResponse {
  token: string
  user: User
}

// ---------- Scout / Radar ----------

export type SignalType =
  | 'funding'
  | 'expansion'
  | 'hiring'
  | 'product_launch'
  | 'leadership_hire'
  | 'merger_acquisition'
  | 'partnership'
  | 'award_recognition'
  | 'other'

export type ICPTier = 'A' | 'B' | 'C' | 'D'

export interface ICPRating {
  score: number // 0-100
  tier: ICPTier | string
  rationale: string
  matched_criteria: string[]
  concerns: string[]
}

export interface Signal {
  signal_type: SignalType | string
  reason_to_target: string
  confidence: number // 0-1
  article_headline: string
  article_url: string
  published_date: string | null
  source_name: string
  discovered_at: string
}

// kept as alias for existing component code
export type CompanySignal = Signal

// Pipeline stage of an account, derived by the backend from the engagement of
// every person inside it (least → most advanced).
export type CompanyStage =
  | 'not_started'
  | 'outreach'
  | 'engaged'
  | 'meeting'
  | 'deal'
  | 'won'
  | 'lost'

export interface CompanyPipeline {
  stage: CompanyStage | string
  people_enrolled: number
  people_engaged: number
  people_met: number
  people_in_deal: number
  open_deals: number
  won_deals: number
  lost_deals: number
  deal_value: number
}

/** Per-person engagement rollup — what the company's stage is derived from. */
export interface CompanyEngagement {
  person_id: string
  name: string
  title: string
  role_category: string
  channels: string[]
  status: string | null
  deal_stage: DealStage | string | null
}

/** A sponsor-bank <-> sponsored-entity edge, summarised. */
export interface SponsorLink {
  company_slug: string
  company_name: string
  industry: string
  fit_score: number
  intent_score: number
  pipeline_stage: string
}

export interface Company {
  id: number
  company_slug: string
  company_name: string
  website_url: string | null
  linkedin_url: string | null
  industry: string
  employee_range: string
  location: string
  signal_type: SignalType | string
  reason_to_target: string | null
  confidence: number
  icp: ICPRating
  /** Structural, durable — can they buy at all. */
  fit_score: number
  /** Timing — is there a reason to call this week. Decays with signal age. */
  intent_score: number
  signal_age_days: number
  qualified: boolean
  source_radar: string
  source_name: string
  article_headline: string
  article_url: string
  published_date: string | null
  discovered_at: string
  people_count: number
  pipeline?: CompanyPipeline
  // present on detail responses
  signals?: Signal[]
  decision_makers?: Person[]
  engagement?: CompanyEngagement[]
  /** Entities this account sponsors (only on sponsor banks). */
  sponsors_portfolio?: SponsorLink[]
  /** Who sponsors this account (only on sponsored entities). */
  sponsored_by?: SponsorLink[]
}

// ---------- Scout / Detective ----------

export type RoleCategory =
  | 'Founder'
  | 'CEO'
  | 'CTO'
  | 'Head of AI'
  | 'VP Engineering'
  | 'Head of Product'

export type EmailStatus = 'verified' | 'guessed' | 'unverified'

export interface PersonStage {
  text: string
  channel: string
  status: string
}

export interface Person {
  id: string
  name: string
  title: string
  role_category: RoleCategory | string
  linkedin_url: string | null
  confidence: number // 0-1
  email: string | null
  email_status: EmailStatus | string | null
  email_source: string | null
  apollo_id: string | null
  city: string | null
  country: string | null
  enriched: boolean
  company_id: number | null
  company_slug: string
  company_name: string
  // list-view engagement fields (may be absent on nested decision_maker rows)
  engagement_status?: string | null
  stage?: PersonStage | null
  company_tier?: string | null
  deal_stage?: DealStage | string | null
}

export interface PersonDetail extends Person {
  company: Company | null
  enrollments: Enrollment[]
  timeline: Event[]
  thread: Message[]
  /** Always present (possibly empty) — meetings are not gated on a deal. */
  meetings: Meeting[]
  /** Present only once the first meeting happened and a deal opened. */
  deal: Deal | null
}

// ---------- Meetings ----------

export type MeetingStatus = 'scheduled' | 'completed' | 'cancelled'

export const MEETING_KINDS = [
  'intro',
  'discovery',
  'demo',
  'technical',
  'pricing',
  'exec',
  'other',
] as const

export type MeetingKind = (typeof MEETING_KINDS)[number]

export interface Meeting {
  id: string
  person_id: string
  deal_id: string | null
  title: string
  kind: MeetingKind | string
  status: MeetingStatus | string
  occurred_at: string
  duration_min: number
  attendees: string[]
  location: string
  sentiment: 'positive' | 'neutral' | 'negative' | string
  notes: string
  summary: string
  source: string
  recording_url: string | null
  has_summary: boolean
  takeaways: string[]
  objections: string[]
  questions: string[]
  commitments: string[]
}

// ---------- Closer / Deals ----------

export type DealStage =
  | 'discovery'
  | 'evaluation'
  | 'proposal'
  | 'negotiation'
  | 'closed_won'
  | 'closed_lost'

export type DealHealth = 'on_track' | 'at_risk' | 'stalled'

export type MeetingPointKind = 'takeaway' | 'objection' | 'question' | 'commitment'

export interface DealNextStep {
  id: string
  step_order: number
  title: string
  detail: string
  owner: string
  due_date: string | null
  priority: 'high' | 'medium' | 'low' | string
  status: 'todo' | 'done' | 'blocked' | string
  rationale: string
}

export interface DealHighlight {
  id: string
  kind: 'strength' | 'risk' | 'blocker' | 'signal' | string
  text: string
  confidence: number
}

export interface Deal {
  id: string
  person_id: string
  company_id: number
  campaign_id: string | null
  stage: DealStage | string
  health: DealHealth | string
  probability: number
  value_usd: number
  owner: string
  source_channel: string
  summary: string
  opened_at: string
  expected_close: string | null
  last_activity_at: string | null
  /** Completed meetings — the meetings themselves live on the contact. */
  meeting_count: number
  open_step_count: number
  next_steps: DealNextStep[]
  highlights: DealHighlight[]
}

// kept as alias — many components/props still reference DecisionMaker
export type DecisionMaker = Person

// ---------- Pulse / Campaigns ----------

export type CampaignStatus =
  | 'draft'
  | 'active'
  | 'paused'
  | 'completed'
  | 'archived'

export type Channel = 'email' | 'linkedin'

export type StepKind = 'invite' | 'message'

export interface Variant {
  id: string
  name: string
  angle: string
  subject_template: string | null
  body_template: string
  sent_count: number
  reply_count: number
  alpha: number
  beta: number
  is_winner: boolean
  is_paused: boolean
}

export interface Step {
  id: string
  step_order: number
  name: string
  angle: string
  wait_days: number
  kind: StepKind | null
  variants: Variant[]
}

export interface Sequence {
  id: string
  channel: Channel
  name: string
  status: string
  steps: Step[]
}

/**
 * How the first touch leaves the building.
 *  - `manual`     — every first touch is held until a human releases that person
 *  - `autonomous` — the engine sends each first touch as soon as it's due
 * Subsequent steps always follow the sequence schedule.
 */
export type SendMode = 'manual' | 'autonomous'

export interface CampaignMetrics {
  enrolled: number
  active: number
  replied: number
  positive: number
  meetings: number
  booked: number
  deals: number
  awaiting_launch: number
  launched: number
  reply_rate: number
  by_status: Record<string, number>
}

export interface Campaign {
  id: string
  name: string
  description: string
  status: CampaignStatus | string
  send_mode: SendMode | string
  icp_min_score: number
  theme: string
  created_at: string
  channels: string[]
  metrics?: CampaignMetrics
  sequences?: Sequence[]
}

// enrollment of a person in a campaign
export interface Enrollment {
  id: string
  campaign_id: string
  sequence_id: string
  channel: Channel
  person_id: string
  name: string
  title: string
  company: string
  company_slug: string
  email: string | null
  linkedin_url: string | null
  role_category: string
  campaign_name: string
  current_step: number
  status: string
  next_action_at: string | null
  last_action_at: string | null
  replied_at: string | null
  enrolled_at: string
  invited_at?: string | null
  accepted_at?: string | null
  launched_at: string | null
  launched_by: string | null
  /** Manual mode is holding this person's first touch. */
  awaiting_launch: boolean
  total_steps?: number
}

// ---------- Activity ----------

export interface Event {
  id: string
  person_id: string
  company_id: number | null
  type: string
  channel: Channel | null
  title: string
  detail: string
  meta?: string
  created_at: string
}

// kept as alias — Timeline component references TimelineEvent
export type TimelineEvent = Event

export interface Message {
  id: string
  person_id: string
  campaign_id: string
  channel: Channel
  direction: 'outbound' | 'inbound'
  step_name: string
  subject: string | null
  body: string
  status: string | null
  reply_class: string | null
  at: string
}

export type MessageThreadItem = Message

// ---------- Aggregates ----------

export interface Stats {
  total_people: number
  total_companies: number
  qualified: number
  contacted: number
  replies: number
  meetings: number
  reply_rate: number
  by_tier: Record<string, number>
  by_signal: Record<string, number>
  open_deals: number
  won_deals: number
  lost_deals: number
  open_deal_value: number
  won_deal_value: number
  by_deal_stage: Record<string, number>
}

// ---------- Pipeline ----------

export type RunStatus = 'running' | 'succeeded' | 'failed'

export interface PipelineRun {
  id: number
  status: RunStatus
  stage: string | null
  companies_found: number
  people_found: number
  enrolled: number
  messages_sent: number
  error: string | null
  started_at: string
  finished_at: string | null
}

// ---------- API response envelopes ----------

export interface Paginated<T> {
  items: T[]
  total: number
  page?: number
  page_size?: number
}

export interface CompanyFacets {
  industries: string[]
  sizes: string[]
  signals: string[]
  stages: string[]
}

export interface PeopleFacets {
  roles: string[]
  companies: { value: string; label: string }[]
  statuses: string[]
}

export interface DashboardData {
  stats: Stats
  top_companies: Company[]
  fresh_signals: Company[]
  recent_activity: Event[]
  active_campaigns: Campaign[]
}

export interface AnalyticsData {
  stats: Stats
  campaigns: Campaign[]
}

export interface SearchResults {
  people: Person[]
  companies: Company[]
  campaigns: Campaign[]
}
