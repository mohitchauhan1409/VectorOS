import { Download } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Button } from '@/components/ui/Button'
import { KpiTile, SectionTitle, LoadingState, ErrorState } from '@/components/ui/Misc'
import { StatusBadge, DealStageBadge, DEAL_STAGE_LABEL } from '@/components/ui/Badge'
import { PipelineErrorBanner } from '@/components/RunPipelineButton'
import * as api from '@/lib/api'
import { useAsync } from '@/lib/useAsync'
import { usePipeline } from '@/lib/pipeline'
import { downloadCsv, stamped } from '@/lib/actions'
import { pct, money, titleCase } from '@/lib/format'

export function AnalyticsPage() {
  const { dataVersion } = usePipeline()
  const { data, loading, error, reload } = useAsync(() => api.getAnalytics(), [dataVersion])

  const header = (
    <PageHeader
      title="Analytics"
      subtitle="Outreach performance across every channel"
      actions={
        <Button
          variant="secondary"
          icon={<Download size={15} />}
          disabled={!data || data.campaigns.length === 0}
          onClick={() =>
            data &&
            downloadCsv(stamped('vector-campaign-performance'), data.campaigns, [
              { header: 'Campaign', value: (c) => c.name },
              { header: 'Channels', value: (c) => c.channels.join(' + ') },
              { header: 'Status', value: (c) => c.status },
              { header: 'Enrolled', value: (c) => c.metrics?.enrolled ?? 0 },
              { header: 'Active', value: (c) => c.metrics?.active ?? 0 },
              { header: 'Replied', value: (c) => c.metrics?.replied ?? 0 },
              { header: 'Meetings', value: (c) => c.metrics?.meetings ?? 0 },
              { header: 'Deals', value: (c) => c.metrics?.deals ?? 0 },
              { header: 'Reply rate', value: (c) => (c.metrics?.reply_rate ?? 0).toFixed(4) },
            ])
          }
        >
          Export CSV
        </Button>
      }
    />
  )

  if (loading && !data) {
    return <div>{header}<LoadingState /></div>
  }
  if (error && !data) {
    return <div>{header}<ErrorState message={error} onRetry={reload} /></div>
  }
  if (!data) return null

  const s = data.stats
  const funnel = [
    { label: 'Qualified', value: s.qualified, color: '#33409B' },
    { label: 'Contacted', value: s.contacted, color: '#3E4FB8' },
    { label: 'Replied', value: s.replies, color: '#2F6FD0' },
    { label: 'Meetings', value: s.meetings, color: '#1F9D57' },
    { label: 'In deal', value: s.open_deals + s.won_deals, color: '#5B3F9E' },
  ]
  const max = Math.max(...funnel.map((f) => f.value), 1)

  return (
    <div>
      {header}
      <PipelineErrorBanner />

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiTile label="Contacted" value={s.contacted.toLocaleString()} />
        <KpiTile label="Reply rate" value={pct(s.reply_rate, 1)} />
        <KpiTile label="Open deals" value={s.open_deals.toLocaleString()} />
        <KpiTile label="Open pipeline value" value={money(s.open_deal_value)} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card p-5">
          <SectionTitle>Conversion funnel</SectionTitle>
          <div className="space-y-3.5">
            {funnel.map((f, i) => {
              const prev = i > 0 ? funnel[i - 1].value : null
              return (
                <div key={f.label}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="text-gray-600">{f.label}</span>
                    <span className="font-semibold text-gray-800 tnum">
                      {f.value.toLocaleString()}
                      {prev !== null && prev > 0 && (
                        <span className="ml-1.5 font-normal text-gray-400">
                          {pct(f.value / prev, 0)} of prev
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-100">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${(f.value / max) * 100}%`, background: f.color }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="card p-5">
          <SectionTitle
            right={
              <span className="text-2xs text-gray-400 tnum">{money(s.open_deal_value)} open</span>
            }
          >
            Deal pipeline
          </SectionTitle>
          {s.open_deals + s.won_deals + s.lost_deals === 0 ? (
            <p className="py-8 text-center text-sm text-gray-400">
              No deals yet. A deal opens once a first meeting has happened.
            </p>
          ) : (
            <div className="space-y-2">
              {Object.entries(s.by_deal_stage)
                .sort(
                  (a, b) =>
                    Object.keys(DEAL_STAGE_LABEL).indexOf(a[0]) -
                    Object.keys(DEAL_STAGE_LABEL).indexOf(b[0]),
                )
                .map(([stage, count]) => (
                  <div key={stage} className="flex items-center justify-between">
                    <DealStageBadge stage={stage} />
                    <span className="text-sm font-medium text-gray-800 tnum">{count}</span>
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card p-5">
          <SectionTitle>Accounts by ICP tier</SectionTitle>
          <Distribution
            data={(['A', 'B', 'C', 'D'] as const).map((t) => ({
              label: `Tier ${t}`,
              value: s.by_tier[t] ?? 0,
            }))}
          />
        </div>
        <div className="card p-5">
          <SectionTitle>Accounts by buying signal</SectionTitle>
          <Distribution
            data={Object.entries(s.by_signal)
              .sort((a, b) => b[1] - a[1])
              .map(([k, v]) => ({ label: titleCase(k), value: v }))}
          />
        </div>
      </div>

      <div className="mt-4 card overflow-hidden">
        <div className="flex items-center justify-between border-b border-hairline px-5 py-3">
          <h3 className="text-sm font-semibold text-gray-800">Campaign performance</h3>
        </div>
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-hairline bg-gray-50 text-2xs font-semibold uppercase tracking-[0.02em] text-gray-500">
              <th className="px-5 py-2.5">Campaign</th>
              <th className="px-4 py-2.5">Channels</th>
              <th className="px-4 py-2.5">Status</th>
              <th className="px-4 py-2.5 text-right">Enrolled</th>
              <th className="px-4 py-2.5 text-right">Replied</th>
              <th className="px-4 py-2.5 text-right">Meetings</th>
              <th className="px-4 py-2.5 text-right">Deals</th>
              <th className="px-4 py-2.5 text-right">Reply rate</th>
            </tr>
          </thead>
          <tbody>
            {data.campaigns.map((c) => {
              const m = c.metrics
              return (
                <tr key={c.id} className="h-12 border-b border-hairline last:border-0 hover:bg-gray-50">
                  <td className="px-5 text-sm font-medium text-gray-800">{c.name}</td>
                  <td className="px-4 text-sm capitalize text-gray-600">{c.channels.join(' · ')}</td>
                  <td className="px-4"><StatusBadge status={c.status} /></td>
                  <td className="px-4 text-right text-sm text-gray-700 tnum">{(m?.enrolled ?? 0).toLocaleString()}</td>
                  <td className="px-4 text-right text-sm text-gray-700 tnum">{(m?.replied ?? 0).toLocaleString()}</td>
                  <td className="px-4 text-right text-sm text-gray-700 tnum">{(m?.meetings ?? 0).toLocaleString()}</td>
                  <td className="px-4 text-right text-sm text-gray-700 tnum">{(m?.deals ?? 0).toLocaleString()}</td>
                  <td className="px-4 text-right text-sm font-medium text-gray-900 tnum">{pct(m?.reply_rate ?? 0, 1)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** Horizontal bar breakdown, sized against the largest value in the set. */
function Distribution({ data }: { data: { label: string; value: number }[] }) {
  const rows = data.filter((d) => d.value > 0)
  if (rows.length === 0) {
    return <p className="py-8 text-center text-sm text-gray-400">No data yet.</p>
  }
  const max = Math.max(...rows.map((d) => d.value))
  const total = rows.reduce((n, d) => n + d.value, 0)
  return (
    <div className="space-y-2.5">
      {rows.map((d) => (
        <div key={d.label}>
          <div className="mb-1 flex items-center justify-between text-xs">
            <span className="truncate text-gray-600">{d.label}</span>
            <span className="shrink-0 font-medium text-gray-800 tnum">
              {d.value}
              <span className="ml-1.5 font-normal text-gray-400">{pct(d.value / total, 0)}</span>
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
            <div
              className="h-full rounded-full bg-brand-600"
              style={{ width: `${(d.value / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
