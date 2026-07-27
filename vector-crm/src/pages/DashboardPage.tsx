import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowUpRight, Rocket } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { KpiTile, SectionTitle, Meter, EmptyState, LoadingState, ErrorState } from '@/components/ui/Misc'
import { Avatar } from '@/components/ui/Avatar'
import { SignalBadge, TierBadge } from '@/components/ui/Badge'
import { SignalIcon } from '@/components/ui/icons'
import { Timeline } from '@/components/Timeline'
import { CompanyDrawer } from '@/components/CompanyDrawer'
import { PersonDrawer } from '@/components/PersonDrawer'
import { RunPipelineButton, PipelineErrorBanner } from '@/components/RunPipelineButton'
import * as api from '@/lib/api'
import { useAsync } from '@/lib/useAsync'
import { usePipeline } from '@/lib/pipeline'
import { pct, relTime, compactNumber, money } from '@/lib/format'

export function DashboardPage() {
  const nav = useNavigate()
  const { dataVersion } = usePipeline()
  const { data, loading, error, reload } = useAsync(() => api.getDashboard(), [dataVersion])
  const [openSlug, setOpenSlug] = useState<string | null>(null)
  const [openPersonId, setOpenPersonId] = useState<string | null>(null)

  if (loading && !data) {
    return (
      <div>
        <PageHeader title="Dashboard" subtitle="Your go-to-market pipeline at a glance" />
        <LoadingState />
      </div>
    )
  }
  if (error && !data) {
    return (
      <div>
        <PageHeader title="Dashboard" subtitle="Your go-to-market pipeline at a glance" />
        <ErrorState message={error} onRetry={reload} />
      </div>
    )
  }
  if (!data) return null

  const s = data.stats
  const isEmpty = s.total_companies === 0 && s.total_people === 0

  if (isEmpty) {
    return (
      <div>
        <PageHeader title="Dashboard" subtitle="Your go-to-market pipeline at a glance" />
        <PipelineErrorBanner />
        <div className="card">
          <EmptyState
            icon={Rocket}
            title="Your workspace is empty"
            description="Vector's engine populates this workspace automatically. Once a pipeline run completes on the backend, your accounts, contacts, and outreach appear here."
            action={<RunPipelineButton />}
          />
        </div>
      </div>
    )
  }

  const funnel = [
    { label: 'Qualified leads', value: s.qualified },
    { label: 'Contacted', value: s.contacted },
    { label: 'Replied', value: s.replies },
    { label: 'Meetings', value: s.meetings },
    { label: 'In deal', value: s.open_deals + s.won_deals },
  ]
  const max = Math.max(...funnel.map((f) => f.value), 1)

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Your go-to-market pipeline at a glance" />
      <PipelineErrorBanner />

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiTile label="Companies tracked" value={s.total_companies.toLocaleString()} />
        <KpiTile label="Contacts sourced" value={s.total_people.toLocaleString()} />
        <KpiTile label="Reply rate" value={pct(s.reply_rate, 1)} sub={`${s.replies} replies`} />
        <KpiTile
          label="Open pipeline"
          value={money(s.open_deal_value)}
          sub={`${s.open_deals} ${s.open_deals === 1 ? 'deal' : 'deals'}`}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Pipeline funnel */}
        <div className="card p-5 lg:col-span-1">
          <SectionTitle>Pipeline</SectionTitle>
          <div className="space-y-3.5">
            {funnel.map((f) => (
              <div key={f.label}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="text-gray-600">{f.label}</span>
                  <span className="font-semibold text-gray-800 tnum">{f.value.toLocaleString()}</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
                  <div className="h-full rounded-full bg-brand-600" style={{ width: `${(f.value / max) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-5">
            <SectionTitle>ICP distribution</SectionTitle>
            <div className="flex gap-2">
              {(['A', 'B', 'C', 'D'] as const).map((t) => (
                <div key={t} className="flex-1 rounded-md border border-hairline p-2 text-center">
                  <div className="text-lg font-bold text-gray-900 tnum">{s.by_tier[t] ?? 0}</div>
                  <div className="mt-0.5"><TierBadge tier={t} /></div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Fresh signals */}
        <div className="card p-5 lg:col-span-2">
          <SectionTitle
            right={
              <button onClick={() => nav('/companies')} className="text-2xs font-medium text-brand-600 hover:underline">
                View all
              </button>
            }
          >
            Fresh buying signals
          </SectionTitle>
          <div className="divide-y divide-hairline">
            {data.fresh_signals.map((c) => (
              <button
                key={c.company_slug}
                onClick={() => setOpenSlug(c.company_slug)}
                className="group flex w-full items-center gap-3 py-2.5 text-left"
              >
                <Avatar name={c.company_name} size="md" square />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-gray-800">{c.company_name}</span>
                    <TierBadge tier={c.icp.tier} />
                  </div>
                  <div className="truncate text-xs text-gray-500">{c.article_headline}</div>
                </div>
                <SignalBadge signal={c.signal_type} icon={<SignalIcon signal={c.signal_type} />} />
                <span className="w-16 shrink-0 text-right text-2xs text-gray-400">{relTime(c.discovered_at)}</span>
                <ArrowUpRight size={14} className="text-gray-300 opacity-0 group-hover:opacity-100" />
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Top accounts */}
        <div className="card p-5 lg:col-span-2">
          <SectionTitle
            right={
              <button onClick={() => nav('/companies')} className="text-2xs font-medium text-brand-600 hover:underline">
                View all
              </button>
            }
          >
            Top accounts by ICP fit
          </SectionTitle>
          <div className="divide-y divide-hairline">
            {data.top_companies.map((c) => (
              <button
                key={c.company_slug}
                onClick={() => setOpenSlug(c.company_slug)}
                className="flex w-full items-center gap-3 py-2.5 text-left"
              >
                <Avatar name={c.company_name} size="sm" square />
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-gray-800">
                  {c.company_name}
                </span>
                <span className="text-xs text-gray-500">{c.people_count} contacts</span>
                <Meter value={c.icp.score} tier={c.icp.tier} />
              </button>
            ))}
          </div>
        </div>

        {/* Active campaigns */}
        <div className="card p-5">
          <SectionTitle
            right={
              <button onClick={() => nav('/campaigns')} className="text-2xs font-medium text-brand-600 hover:underline">
                View all
              </button>
            }
          >
            Active campaigns
          </SectionTitle>
          <div className="space-y-2.5">
            {data.active_campaigns.map((c) => {
              const m = c.metrics
              return (
                <button
                  key={c.id}
                  onClick={() => nav(`/campaigns?id=${c.id}`)}
                  className="w-full rounded-md border border-hairline p-3 text-left transition-colors hover:bg-gray-50"
                >
                  <div className="flex items-center justify-between">
                    <span className="truncate text-sm font-medium text-gray-800">{c.name}</span>
                    <span className="text-xs text-gray-500 tnum">{pct(m?.reply_rate ?? 0, 0)}</span>
                  </div>
                  <div className="mt-1 text-2xs text-gray-500">
                    {compactNumber(m?.enrolled ?? 0)} enrolled · {m?.replied ?? 0} replied
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </div>

      <div className="mt-4 card p-5">
        <SectionTitle>Recent activity</SectionTitle>
        <Timeline events={data.recent_activity} />
      </div>

      <CompanyDrawer
        slug={openSlug}
        onClose={() => setOpenSlug(null)}
        onOpenPerson={(p) => {
          setOpenSlug(null)
          setOpenPersonId(p.id)
        }}
      />
      <PersonDrawer
        personId={openPersonId}
        onClose={() => setOpenPersonId(null)}
        onOpenCompany={(slug) => {
          setOpenPersonId(null)
          setOpenSlug(slug)
        }}
      />
    </div>
  )
}
