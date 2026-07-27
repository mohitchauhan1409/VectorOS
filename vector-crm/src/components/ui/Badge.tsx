import clsx from 'clsx'
import type { ReactNode } from 'react'

export type Tone =
  | 'neutral'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'
  | 'brand'
  | 'violet'
  | 'teal'

const TONES: Record<Tone, string> = {
  neutral: 'bg-gray-100 text-gray-600',
  success: 'bg-success-bg text-success-text',
  warning: 'bg-warning-bg text-warning-text',
  danger: 'bg-danger-bg text-danger-text',
  info: 'bg-info-bg text-info-text',
  brand: 'bg-brand-50 text-brand-700',
  violet: 'bg-[#F3EDFB] text-[#5B3F9E]',
  teal: 'bg-[#E3F1F1] text-[#0E5C5C]',
}

const DOT_COLOR: Partial<Record<string, string>> = {
  active: '#2F6FD0',
  replied: '#33409B',
  in_conversation: '#1F9D57',
  meeting: '#1F9D57',
  booked: '#0F7A3D',
  in_deal: '#5B3F9E',
  not_interested: '#6B7688',
  needs_human: '#C9871B',
  bounced: '#D24141',
  unsubscribed: '#D24141',
  completed: '#6B7688',
}

export function Badge({
  tone = 'neutral',
  children,
  dot = false,
  dotColor,
  icon,
  className,
}: {
  tone?: Tone
  children: ReactNode
  dot?: boolean
  dotColor?: string
  icon?: ReactNode
  className?: string
}) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-xs px-2 h-5 text-2xs font-medium tracking-[0.01em] whitespace-nowrap',
        TONES[tone],
        className,
      )}
    >
      {dot && (
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: dotColor ?? 'currentColor', opacity: dotColor ? 1 : 0.7 }}
        />
      )}
      {icon}
      {children}
    </span>
  )
}

// ---- Domain badge mappings ----

export function EmailStatusBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-gray-400 text-xs">No email</span>
  const map: Record<string, Tone> = {
    verified: 'success',
    guessed: 'warning',
    unverified: 'neutral',
  }
  return (
    <Badge tone={map[status] ?? 'neutral'} dot>
      {status}
    </Badge>
  )
}

export function TierBadge({ tier }: { tier: string }) {
  const map: Record<string, Tone> = { A: 'success', B: 'info', C: 'warning', D: 'neutral' }
  return (
    <Badge tone={map[tier] ?? 'neutral'} className="font-semibold px-1.5">
      {tier}
    </Badge>
  )
}

const SIGNAL_TONE: Record<string, Tone> = {
  funding: 'success',
  hiring: 'info',
  expansion: 'brand',
  product_launch: 'warning',
  leadership_hire: 'violet',
  merger_acquisition: 'warning',
  partnership: 'teal',
  award_recognition: 'violet',
  other: 'neutral',
}

export function SignalBadge({ signal, icon }: { signal: string; icon?: ReactNode }) {
  return (
    <Badge tone={SIGNAL_TONE[signal] ?? 'neutral'} icon={icon}>
      {signal.replace(/_/g, ' ')}
    </Badge>
  )
}

const STATUS_TONE: Record<string, Tone> = {
  active: 'info',
  pending: 'neutral',
  invite_sent: 'info',
  accepted: 'brand',
  replied: 'brand',
  in_conversation: 'success',
  meeting: 'success',
  booked: 'success',
  in_deal: 'violet',
  completed: 'neutral',
  not_interested: 'neutral',
  needs_human: 'warning',
  bounced: 'danger',
  invite_expired: 'danger',
  unsubscribed: 'danger',
  failed: 'danger',
  paused: 'warning',
  draft: 'neutral',
  archived: 'neutral',
}

const STATUS_LABEL: Record<string, string> = { in_deal: 'in deal' }

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={STATUS_TONE[status] ?? 'neutral'} dot dotColor={DOT_COLOR[status]}>
      {STATUS_LABEL[status] ?? status.replace(/_/g, ' ')}
    </Badge>
  )
}

// ---- Closer / deal badges ----

export const DEAL_STAGES = [
  'discovery',
  'evaluation',
  'proposal',
  'negotiation',
  'closed_won',
] as const

const DEAL_STAGE_TONE: Record<string, Tone> = {
  discovery: 'neutral',
  evaluation: 'info',
  proposal: 'brand',
  negotiation: 'violet',
  closed_won: 'success',
  closed_lost: 'danger',
}

export const DEAL_STAGE_LABEL: Record<string, string> = {
  discovery: 'Discovery',
  evaluation: 'Evaluation',
  proposal: 'Proposal',
  negotiation: 'Negotiation',
  closed_won: 'Closed won',
  closed_lost: 'Closed lost',
}

export function DealStageBadge({ stage }: { stage: string }) {
  return (
    <Badge tone={DEAL_STAGE_TONE[stage] ?? 'neutral'} className="font-semibold">
      {DEAL_STAGE_LABEL[stage] ?? stage.replace(/_/g, ' ')}
    </Badge>
  )
}

const HEALTH_TONE: Record<string, Tone> = {
  on_track: 'success',
  at_risk: 'warning',
  stalled: 'danger',
}

export function HealthBadge({ health }: { health: string }) {
  return (
    <Badge tone={HEALTH_TONE[health] ?? 'neutral'} dot>
      {health.replace(/_/g, ' ')}
    </Badge>
  )
}

const PRIORITY_TONE: Record<string, Tone> = { high: 'danger', medium: 'warning', low: 'neutral' }

export function PriorityBadge({ priority }: { priority: string }) {
  return <Badge tone={PRIORITY_TONE[priority] ?? 'neutral'}>{priority}</Badge>
}

const SENTIMENT_TONE: Record<string, Tone> = {
  positive: 'success',
  neutral: 'neutral',
  negative: 'danger',
}

export function SentimentBadge({ sentiment }: { sentiment: string }) {
  return <Badge tone={SENTIMENT_TONE[sentiment] ?? 'neutral'} dot>{sentiment}</Badge>
}

// ---- Company pipeline stage ----

export const COMPANY_STAGES = [
  'not_started',
  'outreach',
  'engaged',
  'meeting',
  'deal',
  'won',
] as const

export const COMPANY_STAGE_LABEL: Record<string, string> = {
  not_started: 'Not started',
  outreach: 'Outreach',
  engaged: 'Engaged',
  meeting: 'Meeting',
  deal: 'In deal',
  won: 'Closed won',
  lost: 'Closed lost',
}

const COMPANY_STAGE_TONE: Record<string, Tone> = {
  not_started: 'neutral',
  outreach: 'info',
  engaged: 'brand',
  meeting: 'teal',
  deal: 'violet',
  won: 'success',
  lost: 'danger',
}

// ---- Sending mode ----

export function SendModeBadge({ mode }: { mode: string }) {
  const autonomous = mode === 'autonomous'
  return (
    <Badge tone={autonomous ? 'success' : 'warning'} dot>
      {autonomous ? 'Autonomous' : 'Manual'}
    </Badge>
  )
}

export function CompanyStageBadge({ stage }: { stage: string }) {
  return (
    <Badge tone={COMPANY_STAGE_TONE[stage] ?? 'neutral'} dot>
      {COMPANY_STAGE_LABEL[stage] ?? stage.replace(/_/g, ' ')}
    </Badge>
  )
}

export function ReplyClassBadge({ rc }: { rc: string }) {
  const map: Record<string, Tone> = {
    interested: 'success',
    objection: 'warning',
    referral: 'info',
    not_interested: 'neutral',
    out_of_office: 'neutral',
    unsubscribe: 'danger',
    auto_reply: 'neutral',
    other: 'neutral',
  }
  return <Badge tone={map[rc] ?? 'neutral'}>{rc.replace(/_/g, ' ')}</Badge>
}

export function CampaignStatusBadge({ status }: { status: string }) {
  return <StatusBadge status={status} />
}
