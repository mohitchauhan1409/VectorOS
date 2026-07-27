import { useMemo, useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Download,
  Check,
  Columns3,
  ArrowUpRight,
  Mail,
  Linkedin,
  Users,
  Copy,
} from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Button } from '@/components/ui/Button'
import { SearchInput } from '@/components/ui/Input'
import { Menu, MenuItem, MenuLabel } from '@/components/ui/Menu'
import { FilterBar, type FilterField, type FilterState } from '@/components/ui/Filters'
import { Segmented } from '@/components/ui/Tabs'
import { Avatar } from '@/components/ui/Avatar'
import { Badge, EmailStatusBadge, StatusBadge, DealStageBadge } from '@/components/ui/Badge'
import { EmptyState, LoadingState, ErrorState, Spinner } from '@/components/ui/Misc'
import { PersonDrawer } from '@/components/PersonDrawer'
import { CompanyDrawer } from '@/components/CompanyDrawer'
import { RunPipelineButton, PipelineErrorBanner } from '@/components/RunPipelineButton'
import * as api from '@/lib/api'
import { useAsync, useDebounced } from '@/lib/useAsync'
import { usePipeline } from '@/lib/pipeline'
import { downloadCsv, stamped, useCopy } from '@/lib/actions'

const PAGE_SIZE = 25

const COLUMNS = [
  { key: 'title', label: 'Title / Role' },
  { key: 'company', label: 'Company' },
  { key: 'email', label: 'Email' },
  { key: 'engagement', label: 'Engagement' },
  { key: 'stage', label: 'Stage' },
] as const

type ColumnKey = (typeof COLUMNS)[number]['key']
const COLUMNS_KEY = 'vector_people_columns'

function loadColumns(): Set<ColumnKey> {
  try {
    const raw = localStorage.getItem(COLUMNS_KEY)
    if (raw) return new Set(JSON.parse(raw) as ColumnKey[])
  } catch {
    /* fall through to defaults */
  }
  return new Set(COLUMNS.map((c) => c.key))
}

export function PeoplePage() {
  const [params, setParams] = useSearchParams()
  const { dataVersion } = usePipeline()
  const [q, setQ] = useState('')
  const [filters, setFilters] = useState<FilterState>({})
  const [compact, setCompact] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [openId, setOpenId] = useState<string | null>(params.get('id'))
  const [companySlug, setCompanySlug] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [visible, setVisible] = useState<Set<ColumnKey>>(loadColumns)
  const { copy, copied } = useCopy()

  const debouncedQ = useDebounced(q, 250)

  const toggleColumn = (key: ColumnKey) => {
    const next = new Set(visible)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    setVisible(next)
    localStorage.setItem(COLUMNS_KEY, JSON.stringify([...next]))
  }
  const shows = (key: ColumnKey) => visible.has(key)

  useEffect(() => {
    const id = params.get('id')
    if (id) setOpenId(id)
  }, [params])

  useEffect(() => setPage(1), [debouncedQ, filters])

  const facets = useAsync(() => api.peopleFacets(), [dataVersion])

  const query = useMemo(
    () => ({
      q: debouncedQ.trim() || undefined,
      role: filters.role,
      email_status: filters.email,
      tier: filters.tier,
      company: filters.company?.[0],
      status: filters.status,
      page,
      page_size: PAGE_SIZE,
    }),
    [debouncedQ, filters, page],
  )

  const { data, loading, error, reload } = useAsync(
    () => api.getPeople(query),
    [query, dataVersion],
  )

  const fields: FilterField[] = useMemo(() => {
    const f = facets.data
    return [
      { key: 'role', label: 'Role', options: (f?.roles ?? []).map((r) => ({ value: r, label: r })) },
      {
        key: 'email',
        label: 'Email status',
        options: ['verified', 'guessed', 'unverified'].map((r) => ({ value: r, label: r })),
      },
      {
        key: 'tier',
        label: 'ICP tier',
        options: ['A', 'B', 'C', 'D'].map((t) => ({ value: t, label: `Tier ${t}` })),
      },
      {
        key: 'status',
        label: 'Engagement',
        options: (f?.statuses ?? []).map((s) => ({ value: s, label: s.replace(/_/g, ' ') })),
      },
      {
        key: 'company',
        label: 'Company',
        options: (f?.companies ?? []).map((c) => ({ value: c.value, label: c.label })),
      },
    ]
  }, [facets.data])

  const rows = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const rowH = compact ? 'h-9' : 'h-[52px]'

  const allSelected = rows.length > 0 && rows.every((p) => selected.has(p.id))
  const toggleAll = () => {
    const next = new Set(selected)
    if (allSelected) rows.forEach((p) => next.delete(p.id))
    else rows.forEach((p) => next.add(p.id))
    setSelected(next)
  }
  const toggleOne = (id: string) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  const setOpen = (id: string | null) => {
    setOpenId(id)
    if (id) setParams({ id }, { replace: true })
    else setParams({}, { replace: true })
  }

  const navPerson = (dir: -1 | 1) => {
    const idx = rows.findIndex((p) => p.id === openId)
    const next = rows[idx + dir]
    if (next) setOpen(next.id)
  }

  const clearAll = () => {
    setFilters({})
    setQ('')
  }

  const hasFiltersOrSearch = Object.keys(filters).length > 0 || !!q.trim()
  const showInitialLoad = loading && !data

  const selectedRows = rows.filter((p) => selected.has(p.id))
  const selectedEmails = selectedRows.map((p) => p.email).filter(Boolean) as string[]

  const csvColumns = [
    { header: 'Name', value: (p: (typeof rows)[number]) => p.name },
    { header: 'Title', value: (p: (typeof rows)[number]) => p.title },
    { header: 'Role', value: (p: (typeof rows)[number]) => p.role_category },
    { header: 'Company', value: (p: (typeof rows)[number]) => p.company_name },
    { header: 'Email', value: (p: (typeof rows)[number]) => p.email ?? '' },
    { header: 'Email status', value: (p: (typeof rows)[number]) => p.email_status ?? '' },
    { header: 'LinkedIn', value: (p: (typeof rows)[number]) => p.linkedin_url ?? '' },
    { header: 'ICP tier', value: (p: (typeof rows)[number]) => p.company_tier ?? '' },
    { header: 'Engagement', value: (p: (typeof rows)[number]) => p.engagement_status ?? '' },
    { header: 'Sequence step', value: (p: (typeof rows)[number]) => p.stage?.text ?? '' },
    { header: 'Deal stage', value: (p: (typeof rows)[number]) => p.deal_stage ?? '' },
  ]

  return (
    <div>
      <PageHeader
        title="People"
        subtitle={`${total.toLocaleString()} contacts across ${facets.data?.companies.length ?? 0} companies`}
        actions={
          <Button
            variant="secondary"
            icon={<Download size={15} />}
            onClick={() => downloadCsv(stamped('vector-people'), rows, csvColumns)}
            disabled={rows.length === 0}
          >
            Export CSV
          </Button>
        }
      />

      <PipelineErrorBanner />

      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <SearchInput value={q} onChange={setQ} placeholder="Search this list…" className="!w-72" />
          <FilterBar fields={fields} state={filters} onChange={setFilters} />
          {loading && data && <Spinner size={14} className="text-gray-400" />}
        </div>
        <div className="flex items-center gap-2">
          <Segmented
            options={[
              { key: 'comfy', label: 'Comfortable' },
              { key: 'compact', label: 'Compact' },
            ]}
            value={compact ? 'compact' : 'comfy'}
            onChange={(k) => setCompact(k === 'compact')}
          />
          <Menu
            width={190}
            trigger={() => (
              <Button variant="secondary" size="md" icon={<Columns3 size={14} />}>
                Columns
              </Button>
            )}
          >
            {() => (
              <>
                <MenuLabel>Visible columns</MenuLabel>
                {COLUMNS.map((c) => (
                  <MenuItem
                    key={c.key}
                    onClick={() => toggleColumn(c.key)}
                    icon={
                      shows(c.key) ? (
                        <Check size={14} className="text-brand-600" />
                      ) : (
                        <span className="block h-3.5 w-3.5" />
                      )
                    }
                  >
                    {c.label}
                  </MenuItem>
                ))}
              </>
            )}
          </Menu>
        </div>
      </div>

      <div className="card overflow-hidden">
        {showInitialLoad ? (
          <LoadingState />
        ) : error && !data ? (
          <ErrorState message={error} onRetry={reload} />
        ) : rows.length === 0 ? (
          hasFiltersOrSearch ? (
            <EmptyState
              icon={Users}
              title="No contacts match these filters."
              description="Try adjusting or clearing your filters to see more people."
              action={<Button variant="secondary" onClick={clearAll}>Clear filters</Button>}
            />
          ) : (
            <EmptyState
              icon={Users}
              title="No contacts yet"
              description="Vector sources decision makers automatically once the engine runs on the backend. They'll appear here as soon as a run completes."
              action={<RunPipelineButton />}
            />
          )
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-hairline bg-gray-50 text-2xs font-semibold uppercase tracking-[0.02em] text-gray-500">
                  <th className="w-11 px-4 py-2.5">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleAll}
                      className="h-3.5 w-3.5 accent-brand-600"
                    />
                  </th>
                  <th className="px-4 py-2.5">Name</th>
                  {shows('title') && <th className="px-4 py-2.5">Title / Role</th>}
                  {shows('company') && <th className="px-4 py-2.5">Company</th>}
                  {shows('email') && <th className="px-4 py-2.5">Email</th>}
                  {shows('engagement') && <th className="px-4 py-2.5">Engagement</th>}
                  {shows('stage') && <th className="px-4 py-2.5">Stage</th>}
                  <th className="w-10 px-4 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => {
                  const isSel = selected.has(p.id)
                  return (
                    <tr
                      key={p.id}
                      onClick={() => setOpen(p.id)}
                      className={`group cursor-pointer border-b border-hairline transition-colors ${
                        isSel ? 'bg-brand-50' : 'hover:bg-gray-50'
                      } ${rowH}`}
                    >
                      <td className="px-4" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isSel}
                          onChange={() => toggleOne(p.id)}
                          className="h-3.5 w-3.5 accent-brand-600"
                        />
                      </td>
                      <td className="px-4">
                        <div className="flex items-center gap-2.5">
                          <Avatar name={p.name} size={compact ? 'sm' : 'md'} />
                          <div className="min-w-0">
                            <div className="truncate text-sm font-medium text-gray-800">{p.name}</div>
                            {!compact && (
                              <div className="truncate text-xs text-gray-500">
                                {p.email ?? 'No email'}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                      {shows('title') && (
                        <td className="px-4">
                          <div className="text-sm text-gray-700">{p.title}</div>
                          {!compact && (
                            <Badge tone="neutral" className="mt-0.5">{p.role_category}</Badge>
                          )}
                        </td>
                      )}
                      {shows('company') && (
                        <td className="px-4">
                          <div className="flex items-center gap-2">
                            <Avatar name={p.company_name} size="xs" square />
                            <span className="truncate text-sm text-gray-700">{p.company_name}</span>
                          </div>
                        </td>
                      )}
                      {shows('email') && (
                        <td className="px-4">
                          <EmailStatusBadge status={p.email_status ?? null} />
                        </td>
                      )}
                      {shows('engagement') && (
                        <td className="px-4">
                          {p.engagement_status ? (
                            <StatusBadge status={p.engagement_status} />
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </td>
                      )}
                      {shows('stage') && (
                        <td className="px-4">
                          {p.deal_stage ? (
                            <DealStageBadge stage={p.deal_stage} />
                          ) : p.stage ? (
                            <span className="inline-flex items-center gap-1.5 text-xs text-gray-600">
                              {p.stage.channel === 'email' ? (
                                <Mail size={13} className="text-gray-400" />
                              ) : (
                                <Linkedin size={13} className="text-gray-400" />
                              )}
                              {p.stage.text}
                            </span>
                          ) : (
                            <span className="text-xs text-gray-400">Not enrolled</span>
                          )}
                        </td>
                      )}
                      <td className="px-4">
                        <ArrowUpRight
                          size={15}
                          className="text-gray-300 opacity-0 transition-opacity group-hover:opacity-100"
                        />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {rows.length > 0 && (
          <div className="flex h-12 items-center justify-between border-t border-hairline px-4 text-sm text-gray-500">
            <span className="tnum">
              Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of{' '}
              {total.toLocaleString()}
            </span>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <span className="px-2 text-xs tnum">
                {page} / {totalPages}
              </span>
              <Button variant="ghost" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Bulk bar */}
      {selected.size > 0 && (
        <div className="fixed bottom-6 left-1/2 z-30 flex -translate-x-1/2 items-center gap-2 rounded-md border border-hairline bg-white px-3 py-2 shadow-md">
          <span className="px-1 text-sm font-medium text-gray-800 tnum">{selected.size} selected</span>
          <span className="h-4 w-px bg-hairline" />
          <Button
            variant="ghost"
            size="sm"
            icon={copied === 'bulk' ? <Check size={14} /> : <Copy size={14} />}
            disabled={selectedEmails.length === 0}
            title={
              selectedEmails.length === 0
                ? 'None of the selected contacts have an email'
                : `Copy ${selectedEmails.length} email addresses`
            }
            onClick={() => void copy(selectedEmails.join(', '), 'bulk')}
          >
            {copied === 'bulk' ? 'Copied' : `Copy ${selectedEmails.length} emails`}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon={<Mail size={14} />}
            disabled={selectedEmails.length === 0}
            onClick={() => {
              window.location.href = `mailto:?bcc=${encodeURIComponent(selectedEmails.join(','))}`
            }}
          >
            Compose
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon={<Download size={14} />}
            onClick={() => downloadCsv(stamped('vector-people-selection'), selectedRows, csvColumns)}
          >
            Export
          </Button>
          <span className="h-4 w-px bg-hairline" />
          <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>Clear</Button>
        </div>
      )}

      <PersonDrawer
        personId={openId}
        onClose={() => setOpen(null)}
        onNav={navPerson}
        onOpenCompany={(slug) => {
          setOpen(null)
          setCompanySlug(slug)
        }}
      />
      <CompanyDrawer
        slug={companySlug}
        onClose={() => setCompanySlug(null)}
        onOpenPerson={(p) => {
          setCompanySlug(null)
          setOpen(p.id)
        }}
      />
    </div>
  )
}
