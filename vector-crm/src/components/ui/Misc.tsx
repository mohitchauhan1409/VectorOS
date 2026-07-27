import clsx from 'clsx'
import { ArrowUp, ArrowDown, Loader2, AlertCircle } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

export function Spinner({ size = 16, className }: { size?: number; className?: string }) {
  return <Loader2 size={size} className={clsx('animate-spin', className)} />
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-gray-400">
      <Spinner size={22} />
      <span className="text-sm">{label}</span>
    </div>
  )
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string
  onRetry?: () => void
}) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center py-12 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-md bg-danger-bg">
        <AlertCircle size={28} strokeWidth={1.5} className="text-danger-text" />
      </div>
      <h3 className="mt-4 text-base font-semibold text-gray-800">Couldn’t load this data</h3>
      <p className="mt-1.5 text-sm text-gray-500">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 inline-flex h-8 items-center rounded-sm border border-hairline-strong px-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Try again
        </button>
      )}
    </div>
  )
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center py-12 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-md bg-gray-100">
        <Icon size={28} strokeWidth={1.5} className="text-gray-400" />
      </div>
      <h3 className="mt-4 text-base font-semibold text-gray-800">{title}</h3>
      <p className="mt-1.5 text-sm text-gray-500">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function KpiTile({
  label,
  value,
  delta,
  deltaGood,
  sub,
}: {
  label: string
  value: string
  delta?: string
  deltaGood?: boolean
  sub?: string
}) {
  return (
    <div className="card p-4">
      <div className="section-label">{label}</div>
      <div className="mt-2 text-3xl font-heavy text-gray-900 tnum leading-none">{value}</div>
      {(delta || sub) && (
        <div className="mt-2.5 flex items-center gap-1.5">
          {delta && (
            <span
              className={clsx(
                'inline-flex items-center gap-0.5 text-xs font-medium',
                deltaGood ? 'text-success-text' : 'text-danger-text',
              )}
            >
              {deltaGood ? <ArrowUp size={12} /> : <ArrowDown size={12} />}
              {delta}
            </span>
          )}
          {sub && <span className="text-xs text-gray-500">{sub}</span>}
        </div>
      )}
    </div>
  )
}

export function KeyValue({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-1.5">
      <div className="w-28 shrink-0 pt-0.5 text-2xs font-semibold uppercase tracking-[0.04em] text-gray-500">
        {label}
      </div>
      <div className="min-w-0 flex-1 text-sm text-gray-800">{children}</div>
    </div>
  )
}

export function Meter({ value, tier }: { value: number; tier: string }) {
  const color: Record<string, string> = {
    A: '#116335',
    B: '#1E4A8F',
    C: '#8A5A0B',
    D: '#6B7688',
  }
  return (
    <div className="flex items-center gap-2">
      <span className="w-6 text-sm font-medium text-gray-800 tnum">{value}</span>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-100">
        <div
          className="h-full rounded-full"
          style={{ width: `${value}%`, background: color[tier] ?? '#6B7688' }}
        />
      </div>
    </div>
  )
}

/**
 * Fit and Intent side by side. Deliberately two numbers: fit is structural and
 * durable, intent decays with signal age. Averaging them hides the distinction an
 * SDR most needs — "great account, nothing happening" vs "call this week".
 */
export function FitIntent({
  fit,
  intent,
  ageDays,
}: {
  fit: number
  intent: number
  ageDays?: number
}) {
  const hot = intent >= 55
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-baseline gap-1">
        <span className="text-2xs uppercase tracking-[0.04em] text-gray-400">Fit</span>
        <span className="text-sm font-semibold text-gray-900 tnum">{fit}</span>
      </div>
      <span className="h-3 w-px bg-hairline" />
      <div className="flex items-baseline gap-1">
        <span className="text-2xs uppercase tracking-[0.04em] text-gray-400">Intent</span>
        <span
          className={clsx('text-sm font-semibold tnum', hot ? 'text-success-text' : 'text-gray-500')}
        >
          {intent}
        </span>
      </div>
      {ageDays !== undefined && (
        <span className="text-2xs text-gray-400">
          {ageDays === 0 ? 'today' : `${ageDays}d ago`}
        </span>
      )}
    </div>
  )
}

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h4 className="text-2xs font-semibold uppercase tracking-[0.04em] text-gray-500">{children}</h4>
      {right}
    </div>
  )
}
