import { useMemo, useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Download, ArrowUpRight, Building2, ArrowDownUp } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Button } from '@/components/ui/Button'
import { SearchInput } from '@/components/ui/Input'
import { Menu, MenuItem, MenuLabel } from '@/components/ui/Menu'
import { FilterBar, type FilterField, type FilterState } from '@/components/ui/Filters'
import { SignalBadge, TierBadge, CompanyStageBadge, COMPANY_STAGE_LABEL } from '@/components/ui/Badge'
import { EmptyState, FitIntent, LoadingState, ErrorState, Spinner } from '@/components/ui/Misc'
import { Avatar } from '@/components/ui/Avatar'
import { SignalIcon } from '@/components/ui/icons'
import { CompanyDrawer } from '@/components/CompanyDrawer'
import { PersonDrawer } from '@/components/PersonDrawer'
import { RunPipelineButton, PipelineErrorBanner } from '@/components/RunPipelineButton'
import * as api from '@/lib/api'
import { useAsync, useDebounced } from '@/lib/useAsync'
import { usePipeline } from '@/lib/pipeline'
import { downloadCsv, stamped } from '@/lib/actions'
import { relTime, money } from '@/lib/format'

const SORTS = [
  { key: 'icp', label: 'Fit score' },
  { key: 'intent', label: 'Intent (timing)' },
  { key: 'recent', label: 'Most recent' },
  { key: 'stage', label: 'Pipeline stage' },
] as const

type Sort = (typeof SORTS)[number]['key']

export function CompaniesPage() {
  const [params, setParams] = useSearchParams()
  const { dataVersion } = usePipeline()
  const [q, setQ] = useState('')
  const [filters, setFilters] = useState<FilterState>({})
  const [openSlug, setOpenSlug] = useState<string | null>(params.get('slug'))
  const [openPersonId, setOpenPersonId] = useState<string | null>(null)
  const [sort, setSort] = useState<Sort>('icp')

  const debouncedQ = useDebounced(q, 250)

  useEffect(() => {
    const slug = params.get('slug')
    if (slug) setOpenSlug(slug)
  }, [params])

  const facets = useAsync(() => api.companyFacets(), [dataVersion])

  const query = useMemo(
    () => ({
      q: debouncedQ.trim() || undefined,
      sort,
      tier: filters.tier,
      signal: filters.signal,
      industry: filters.industry,
      size: filters.size,
      stage: filters.stage,
    }),
    [debouncedQ, sort, filters],
  )

  const { data, loading, error, reload } = useAsync(
    () => api.getCompanies(query),
    [query, dataVersion],
  )

  const fields: FilterField[] = useMemo(() => {
    const f = facets.data
    return [
      { key: 'tier', label: 'ICP tier', options: ['A', 'B', 'C', 'D'].map((t) => ({ value: t, label: `Tier ${t}` })) },
      {
        key: 'stage',
        label: 'Pipeline stage',
        options: (f?.stages ?? []).map((s) => ({
          value: s,
          label: COMPANY_STAGE_LABEL[s] ?? s.replace(/_/g, ' '),
        })),
      },
      {
        key: 'signal',
        label: 'Signal',
        options: (f?.signals ?? []).map((s) => ({ value: s, label: s.replace(/_/g, ' ') })),
      },
      {
        key: 'industry',
        label: 'Industry',
        options: (f?.industries ?? []).map((i) => ({ value: i, label: i })),
      },
      {
        key: 'size',
        label: 'Employees',
        options: (f?.sizes ?? []).map((i) => ({ value: i, label: i })),
      },
    ]
  }, [facets.data])

  const rows = data?.items ?? []
  const total = data?.total ?? 0
  const qualified = rows.filter((c) => c.qualified).length
  const inDeal = rows.filter((c) => c.pipeline?.stage === 'deal').length

  const exportCsv = () =>
    downloadCsv(stamped('vector-companies'), rows, [
      { header: 'Company', value: (c) => c.company_name },
      { header: 'Website', value: (c) => c.website_url ?? '' },
      { header: 'Industry', value: (c) => c.industry },
      { header: 'Employees', value: (c) => c.employee_range },
      { header: 'Location', value: (c) => c.location },
      { header: 'Fit score', value: (c) => c.fit_score },
      { header: 'Intent score', value: (c) => c.intent_score },
      { header: 'Signal age (days)', value: (c) => c.signal_age_days },
      { header: 'Tier', value: (c) => c.icp.tier },
      { header: 'Signal', value: (c) => c.signal_type },
      { header: 'Pipeline stage', value: (c) => c.pipeline?.stage ?? '' },
      { header: 'Open deals', value: (c) => c.pipeline?.open_deals ?? 0 },
      { header: 'Deal value', value: (c) => c.pipeline?.deal_value ?? 0 },
      { header: 'Contacts', value: (c) => c.people_count },
      { header: 'Discovered', value: (c) => c.discovered_at },
    ])

  const setOpen = (slug: string | null) => {
    setOpenSlug(slug)
    setParams(slug ? { slug } : {}, { replace: true })
  }

  const clearAll = () => {
    setFilters({})
    setQ('')
  }

  const hasFiltersOrSearch = Object.keys(filters).length > 0 || !!q.trim()
  const showInitialLoad = loading && !data

  return (
    <div>
      <PageHeader
        title="Companies"
        subtitle={`${total} accounts · ${qualified} qualified${inDeal ? ` · ${inDeal} in deal` : ''}`}
        actions={
          <Button
            variant="secondary"
            icon={<Download size={15} />}
            onClick={exportCsv}
            disabled={rows.length === 0}
          >
            Export CSV
          </Button>
        }
      />

      <PipelineErrorBanner />

      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <SearchInput value={q} onChange={setQ} placeholder="Search companies…" className="!w-72" />
          <FilterBar fields={fields} state={filters} onChange={setFilters} />
          {loading && data && <Spinner size={14} className="text-gray-400" />}
        </div>
        <Menu
          width={180}
          trigger={() => (
            <Button variant="secondary" icon={<ArrowDownUp size={14} />}>
              Sort: {SORTS.find((s) => s.key === sort)?.label}
            </Button>
          )}
        >
          {(close) => (
            <>
              <MenuLabel>Sort by</MenuLabel>
              {SORTS.map((s) => (
                <MenuItem
                  key={s.key}
                  onClick={() => {
                    setSort(s.key)
                    close()
                  }}
                  hint={sort === s.key ? '✓' : undefined}
                >
                  {s.label}
                </MenuItem>
              ))}
            </>
          )}
        </Menu>
      </div>

      <div className="card overflow-hidden">
        {showInitialLoad ? (
          <LoadingState />
        ) : error && !data ? (
          <ErrorState message={error} onRetry={reload} />
        ) : rows.length === 0 ? (
          hasFiltersOrSearch ? (
            <EmptyState
              icon={Building2}
              title="No companies match these filters."
              description="Adjust or clear your filters to see more accounts."
              action={<Button variant="secondary" onClick={clearAll}>Clear filters</Button>}
            />
          ) : (
            <EmptyState
              icon={Building2}
              title="No companies yet"
              description="Vector discovers in-market accounts from live buying signals automatically. They'll appear here once the engine runs on the backend."
              action={<RunPipelineButton />}
            />
          )
        ) : (
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-hairline bg-gray-50 text-2xs font-semibold uppercase tracking-[0.02em] text-gray-500">
                <th className="px-4 py-2.5">Company</th>
                <th className="px-4 py-2.5">Fit / Intent</th>
                <th className="w-16 px-4 py-2.5">Tier</th>
                <th className="px-4 py-2.5">Stage</th>
                <th className="px-4 py-2.5">Signal</th>
                <th className="px-4 py-2.5">Contacts</th>
                <th className="w-10 px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr
                  key={c.company_slug}
                  onClick={() => setOpen(c.company_slug)}
                  className="group h-[52px] cursor-pointer border-b border-hairline transition-colors hover:bg-gray-50"
                >
                  <td className="px-4">
                    <div className="flex items-center gap-2.5">
                      <Avatar name={c.company_name} size="md" square />
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-gray-800">{c.company_name}</div>
                        <div className="truncate text-xs text-gray-500">
                          {c.website_url?.replace('https://', '')}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4">
                    <FitIntent fit={c.fit_score} intent={c.intent_score} ageDays={c.signal_age_days} />
                  </td>
                  <td className="px-4">
                    <TierBadge tier={c.icp.tier} />
                  </td>
                  <td className="px-4">
                    <div className="flex flex-col items-start gap-0.5">
                      <CompanyStageBadge stage={c.pipeline?.stage ?? 'not_started'} />
                      {(c.pipeline?.deal_value ?? 0) > 0 && (
                        <span className="text-2xs font-medium text-[#5B3F9E] tnum">
                          {money(c.pipeline!.deal_value)}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4">
                    <div className="flex flex-col items-start gap-0.5">
                      <SignalBadge signal={c.signal_type} icon={<SignalIcon signal={c.signal_type} />} />
                      <span className="text-2xs text-gray-400">{relTime(c.discovered_at)}</span>
                    </div>
                  </td>
                  <td className="px-4">
                    {c.people_count > 0 ? (
                      <span className="text-sm text-gray-700 tnum">{c.people_count}</span>
                    ) : (
                      <span className="text-xs text-gray-400">None</span>
                    )}
                  </td>
                  <td className="px-4">
                    <ArrowUpRight
                      size={15}
                      className="text-gray-300 opacity-0 transition-opacity group-hover:opacity-100"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {rows.length > 0 && (
          <div className="flex h-12 items-center border-t border-hairline px-4 text-sm text-gray-500">
            <span className="tnum">Showing {rows.length} of {total} companies</span>
          </div>
        )}
      </div>

      <CompanyDrawer
        slug={openSlug}
        onClose={() => setOpen(null)}
        onOpenPerson={(p) => {
          setOpen(null)
          setOpenPersonId(p.id)
        }}
      />
      <PersonDrawer
        personId={openPersonId}
        onClose={() => setOpenPersonId(null)}
        onOpenCompany={(slug) => {
          setOpenPersonId(null)
          setOpen(slug)
        }}
      />
    </div>
  )
}
