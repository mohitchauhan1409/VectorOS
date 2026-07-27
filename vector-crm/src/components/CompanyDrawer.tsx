import { useEffect, useState } from 'react'
import clsx from 'clsx'
import {
  X,
  Maximize2,
  Minimize2,
  Ellipsis,
  ArrowUpRight,
  Linkedin,
  Globe,
  Copy,
  Check,
  Link2,
  Download,
  Handshake,
  Mail,
  ArrowRight,
} from 'lucide-react'
import { Drawer } from '@/components/ui/Drawer'
import { Avatar } from '@/components/ui/Avatar'
import { Button, IconButton } from '@/components/ui/Button'
import { Menu, MenuItem, MenuLabel, MenuSeparator } from '@/components/ui/Menu'
import { Tabs } from '@/components/ui/Tabs'
import {
  Badge,
  SignalBadge,
  EmailStatusBadge,
  StatusBadge,
  DealStageBadge,
  CompanyStageBadge,
  COMPANY_STAGES,
  COMPANY_STAGE_LABEL,
} from '@/components/ui/Badge'
import { KeyValue, SectionTitle, Meter, FitIntent, LoadingState, ErrorState } from '@/components/ui/Misc'
import { SignalIcon } from '@/components/ui/icons'
import * as api from '@/lib/api'
import { useAsync } from '@/lib/useAsync'
import { downloadCsv, stamped, useCopy } from '@/lib/actions'
import { dateOnly, money } from '@/lib/format'
import type { Company, CompanyEngagement, Person } from '@/lib/types'

export function CompanyDrawer({
  slug,
  onClose,
  onOpenPerson,
}: {
  slug: string | null
  onClose: () => void
  onOpenPerson?: (p: Person) => void
}) {
  const [tab, setTab] = useState('overview')
  const [expanded, setExpanded] = useState(false)
  const { copy, copied } = useCopy()
  const { data: company, loading, error, reload } = useAsync(
    async () => (slug ? api.getCompany(slug) : null),
    [slug],
  )

  useEffect(() => setTab('overview'), [slug])

  if (!slug) return null

  const dms = company?.decision_makers ?? []
  const signals = company?.signals ?? []
  const pipeline = company?.pipeline ?? null
  const engagement = company?.engagement ?? []

  return (
    <Drawer open={!!slug} onClose={onClose} width={expanded ? 900 : 620}>
      {loading || !company ? (
        error ? (
          <div className="flex flex-1 items-center justify-center">
            <ErrorState message={error} onRetry={reload} />
          </div>
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <LoadingState label="Loading company…" />
          </div>
        )
      ) : (
        <>
          <div className="flex items-start gap-3 border-b border-hairline px-6 py-4">
            <Avatar name={company.company_name} size="xl" square />
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-xl font-semibold text-gray-900">{company.company_name}</h2>
              <p className="truncate text-sm text-gray-500">
                {company.website_url?.replace('https://', '')} · {company.industry}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Meter value={company.icp.score} tier={company.icp.tier} />
                <span className="text-xs text-gray-500">Tier {company.icp.tier}</span>
                <FitIntent
                  fit={company.fit_score}
                  intent={company.intent_score}
                  ageDays={company.signal_age_days}
                />
                {pipeline && <CompanyStageBadge stage={pipeline.stage} />}
              </div>
            </div>
            <div className="flex items-center gap-0.5">
              <IconButton
                aria-label={expanded ? 'Collapse panel' : 'Expand panel'}
                title={expanded ? 'Collapse panel' : 'Expand panel'}
                onClick={() => setExpanded((e) => !e)}
              >
                {expanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
              </IconButton>
              <Menu trigger={() => <IconButton aria-label="More"><Ellipsis size={16} /></IconButton>}>
                {(close) => (
                  <>
                    <MenuLabel>Copy</MenuLabel>
                    {company.website_url && (
                      <MenuItem
                        icon={<Globe size={14} />}
                        onClick={() => {
                          void copy(company.website_url!, 'site')
                          close()
                        }}
                      >
                        Website URL
                      </MenuItem>
                    )}
                    {company.linkedin_url && (
                      <MenuItem
                        icon={<Linkedin size={14} />}
                        onClick={() => {
                          void copy(company.linkedin_url!, 'li')
                          close()
                        }}
                      >
                        LinkedIn URL
                      </MenuItem>
                    )}
                    <MenuItem
                      icon={<Link2 size={14} />}
                      onClick={() => {
                        void copy(
                          `${window.location.origin}/companies?slug=${company.company_slug}`,
                          'link',
                        )
                        close()
                      }}
                    >
                      Link to account
                    </MenuItem>
                    <MenuSeparator />
                    <MenuItem
                      icon={<Mail size={14} />}
                      disabled={dms.filter((p) => p.email).length === 0}
                      onClick={() => {
                        void copy(
                          dms.filter((p) => p.email).map((p) => p.email).join(', '),
                          'emails',
                        )
                        close()
                      }}
                    >
                      All contact emails
                    </MenuItem>
                    <MenuItem
                      icon={<Download size={14} />}
                      disabled={dms.length === 0}
                      onClick={() => {
                        downloadCsv(stamped(`${company.company_slug}-contacts`), dms, [
                          { header: 'Name', value: (p) => p.name },
                          { header: 'Title', value: (p) => p.title },
                          { header: 'Role', value: (p) => p.role_category },
                          { header: 'Email', value: (p) => p.email ?? '' },
                          { header: 'Email status', value: (p) => p.email_status ?? '' },
                          { header: 'LinkedIn', value: (p) => p.linkedin_url ?? '' },
                        ])
                        close()
                      }}
                    >
                      Export contacts (CSV)
                    </MenuItem>
                  </>
                )}
              </Menu>
              <IconButton aria-label="Close" onClick={onClose}><X size={16} /></IconButton>
            </div>
          </div>

          <div className="flex items-center gap-2 border-b border-hairline px-6 py-3">
            <Button
              variant="primary"
              size="sm"
              icon={copied === 'emails' ? <Check size={14} /> : <Mail size={14} />}
              disabled={dms.filter((p) => p.email).length === 0}
              onClick={() =>
                void copy(dms.filter((p) => p.email).map((p) => p.email).join(', '), 'emails')
              }
            >
              {copied === 'emails' ? 'Copied' : 'Copy emails'}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              icon={<Download size={14} />}
              disabled={dms.length === 0}
              onClick={() =>
                downloadCsv(stamped(`${company.company_slug}-contacts`), dms, [
                  { header: 'Name', value: (p) => p.name },
                  { header: 'Title', value: (p) => p.title },
                  { header: 'Role', value: (p) => p.role_category },
                  { header: 'Email', value: (p) => p.email ?? '' },
                  { header: 'Email status', value: (p) => p.email_status ?? '' },
                  { header: 'LinkedIn', value: (p) => p.linkedin_url ?? '' },
                ])
              }
            >
              Export
            </Button>
            <div className="flex-1" />
            {company.website_url && (
              <IconButton
                aria-label="Open website"
                title="Open website"
                size="sm"
                onClick={() => window.open(company.website_url!, '_blank', 'noopener')}
              >
                <Globe size={15} />
              </IconButton>
            )}
            {company.linkedin_url && (
              <IconButton
                aria-label="Open LinkedIn"
                title="Open LinkedIn"
                size="sm"
                onClick={() => window.open(company.linkedin_url!, '_blank', 'noopener')}
              >
                <Linkedin size={15} />
              </IconButton>
            )}
          </div>

          <div className="px-6">
            <Tabs
              tabs={[
                { key: 'overview', label: 'Overview' },
                { key: 'pipeline', label: 'Pipeline' },
                { key: 'signals', label: 'Signals', count: signals.length },
                { key: 'people', label: 'People', count: dms.length },
                { key: 'icp', label: 'ICP' },
              ]}
              active={tab}
              onChange={setTab}
            />
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-4">
            {tab === 'overview' && (
              <div className="space-y-6">
                {pipeline && (
                  <button
                    onClick={() => setTab('pipeline')}
                    className="group w-full rounded-md border border-hairline p-3 text-left transition-colors hover:border-hairline-strong"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-2xs font-semibold uppercase tracking-[0.04em] text-gray-500">
                        Pipeline stage
                      </span>
                      <CompanyStageBadge stage={pipeline.stage} />
                      {pipeline.deal_value > 0 && (
                        <Badge tone="violet">{money(pipeline.deal_value)}</Badge>
                      )}
                      <ArrowRight
                        size={14}
                        className="ml-auto text-gray-400 transition-transform group-hover:translate-x-0.5"
                      />
                    </div>
                    <div className="mt-2.5">
                      <StageRail stage={pipeline.stage} />
                    </div>
                  </button>
                )}

                <section>
                  <SectionTitle>Firmographics</SectionTitle>
                  <div className="divide-y divide-hairline">
                    <KeyValue label="Website">
                      <a href={company.website_url ?? '#'} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand-600 hover:underline">
                        {company.website_url?.replace('https://', '')} <ArrowUpRight size={13} />
                      </a>
                    </KeyValue>
                    <KeyValue label="Industry">{company.industry}</KeyValue>
                    <KeyValue label="Employees">{company.employee_range}</KeyValue>
                    <KeyValue label="Location">{company.location}</KeyValue>
                    <KeyValue label="Discovered">{dateOnly(company.discovered_at)}</KeyValue>
                    <KeyValue label="Qualified">
                      {company.qualified ? (
                        <Badge tone="success">Qualified</Badge>
                      ) : (
                        <Badge tone="neutral">Not qualified</Badge>
                      )}
                    </KeyValue>
                  </div>
                </section>

                <section>
                  <SectionTitle>Primary signal</SectionTitle>
                  <div className="rounded-md border border-hairline p-3">
                    <div className="flex items-center justify-between">
                      <SignalBadge signal={company.signal_type} icon={<SignalIcon signal={company.signal_type} />} />
                      <span className="text-2xs text-gray-400">{company.source_name}</span>
                    </div>
                    <p className="mt-2 text-sm text-gray-600">{company.reason_to_target}</p>
                    <p className="mt-2 text-xs font-medium text-gray-700">{company.article_headline}</p>
                  </div>
                </section>

                <section>
                  <SectionTitle right={<span className="text-2xs text-gray-400">{dms.length}</span>}>
                    Decision makers
                  </SectionTitle>
                  {dms.length === 0 ? (
                    <p className="text-sm text-gray-400">No contacts sourced yet.</p>
                  ) : (
                    <div className="space-y-1">
                      {dms.map((p) => (
                        <PersonRow key={p.id} person={p} onClick={() => onOpenPerson?.(p)} />
                      ))}
                    </div>
                  )}
                </section>
              </div>
            )}

            {tab === 'pipeline' && (
              <PipelineTab
                company={company}
                engagement={engagement}
                onOpenPerson={(id) => {
                  const p = dms.find((x) => x.id === id)
                  if (p) onOpenPerson?.(p)
                }}
              />
            )}

            {tab === 'signals' && (
              <div className="space-y-3">
                {signals.length === 0 ? (
                  <p className="text-sm text-gray-400">No signals recorded.</p>
                ) : (
                  signals.map((s, i) => (
                    <div key={i} className="rounded-md border border-hairline p-3">
                      <div className="flex items-center justify-between">
                        <SignalBadge signal={s.signal_type} icon={<SignalIcon signal={s.signal_type} />} />
                        <span className="text-2xs text-gray-400">{s.published_date}</span>
                      </div>
                      <p className="mt-2 text-sm font-medium text-gray-800">{s.article_headline}</p>
                      <p className="mt-1 text-sm text-gray-500 line-clamp-3">{s.reason_to_target}</p>
                      <div className="mt-2 flex items-center justify-between text-2xs text-gray-400">
                        <span>{s.source_name}</span>
                        <span>Confidence {Math.round(s.confidence * 100)}%</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {tab === 'people' && (
              <div className="space-y-1">
                {dms.length === 0 ? (
                  <p className="text-sm text-gray-400">No contacts sourced yet.</p>
                ) : (
                  dms.map((p) => (
                    <PersonRow key={p.id} person={p} onClick={() => onOpenPerson?.(p)} expanded />
                  ))
                )}
              </div>
            )}

            {tab === 'icp' && (
              <div className="space-y-6">
                <section>
                  <SectionTitle>Rationale</SectionTitle>
                  <p className="text-sm text-gray-600">{company.icp.rationale}</p>
                </section>
                <section>
                  <SectionTitle>Matched criteria</SectionTitle>
                  <ul className="space-y-1.5">
                    {company.icp.matched_criteria.map((c, i) => (
                      <li key={i} className="flex gap-2 text-sm text-gray-700">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-success" />
                        {c}
                      </li>
                    ))}
                  </ul>
                </section>
                <section>
                  <SectionTitle>Concerns</SectionTitle>
                  <ul className="space-y-1.5">
                    {company.icp.concerns.map((c, i) => (
                      <li key={i} className="flex gap-2 text-sm text-gray-700">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-warning" />
                        {c}
                      </li>
                    ))}
                  </ul>
                </section>
              </div>
            )}
          </div>
        </>
      )}
    </Drawer>
  )
}

/** Horizontal progress rail across the account pipeline stages. */
function StageRail({ stage }: { stage: string }) {
  const lost = stage === 'lost'
  const idx = COMPANY_STAGES.indexOf(stage as (typeof COMPANY_STAGES)[number])
  if (lost) {
    return (
      <div className="rounded-sm bg-danger-bg px-2.5 py-1.5 text-2xs text-danger-text">
        Every deal on this account closed lost.
      </div>
    )
  }
  return (
    <div className="flex gap-1">
      {COMPANY_STAGES.map((s, i) => (
        <div key={s} className="min-w-0 flex-1">
          <div
            className={clsx(
              'h-1.5 rounded-full',
              i < idx ? 'bg-brand-600' : i === idx ? 'bg-brand-500' : 'bg-gray-100',
            )}
          />
          <div
            className={clsx(
              'mt-1.5 truncate text-[10px] leading-tight',
              i === idx ? 'font-semibold text-gray-800' : 'text-gray-400',
            )}
          >
            {COMPANY_STAGE_LABEL[s]}
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * Where the account actually stands — the stage plus the per-person engagement
 * it is derived from.
 */
function PipelineTab({
  company,
  engagement,
  onOpenPerson,
}: {
  company: Company
  engagement: CompanyEngagement[]
  onOpenPerson: (personId: string) => void
}) {
  const p = company.pipeline
  if (!p) return <p className="text-sm text-gray-400">No pipeline data for this account.</p>

  const contacted = engagement.filter((e) => e.status)
  const untouched = engagement.filter((e) => !e.status)

  return (
    <div className="space-y-6">
      <section>
        <SectionTitle right={<CompanyStageBadge stage={p.stage} />}>Account stage</SectionTitle>
        <div className="rounded-md border border-hairline p-3">
          <StageRail stage={p.stage} />
          <p className="mt-3 text-xs leading-relaxed text-gray-500">
            Derived from the furthest-along engagement across this account's{' '}
            {company.people_count} known {company.people_count === 1 ? 'contact' : 'contacts'}.
          </p>
        </div>
      </section>

      <section>
        <SectionTitle>Rollup</SectionTitle>
        <div className="grid grid-cols-4 gap-2">
          <Stat label="Enrolled" value={p.people_enrolled} />
          <Stat label="Engaged" value={p.people_engaged} />
          <Stat label="Met" value={p.people_met} />
          <Stat label="In deal" value={p.people_in_deal} accent={p.people_in_deal > 0} />
        </div>
        {(p.open_deals > 0 || p.won_deals > 0 || p.lost_deals > 0) && (
          <div className="mt-3 flex items-center justify-between rounded-md border border-[#DCD2F0] bg-[#F8F5FE] px-3 py-2.5">
            <span className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-800">
              <Handshake size={14} className="text-[#5B3F9E]" />
              {p.open_deals} open {p.open_deals === 1 ? 'deal' : 'deals'}
              {p.won_deals > 0 && ` · ${p.won_deals} won`}
              {p.lost_deals > 0 && ` · ${p.lost_deals} lost`}
            </span>
            <span className="text-sm font-semibold text-gray-900 tnum">{money(p.deal_value)}</span>
          </div>
        )}
      </section>

      {(company.sponsors_portfolio?.length || company.sponsored_by?.length) ? (
        <section>
          <SectionTitle>Sponsorship</SectionTitle>
          {company.sponsored_by?.length ? (
            <div className="rounded-md border border-[#E5C98F] bg-warning-bg p-3">
              <p className="text-xs leading-relaxed text-warning-text">
                Sponsored by{' '}
                <strong className="font-semibold">
                  {company.sponsored_by.map((x) => x.company_name).join(', ')}
                </strong>
                . The collateral formula is likely set upstream — if so, the decision sits with
                the sponsor, not here.
              </p>
            </div>
          ) : null}
          {company.sponsors_portfolio?.length ? (
            <div className="mt-2 rounded-md border border-[#DCD2F0] bg-[#F8F5FE] p-3">
              <p className="mb-2 text-xs leading-relaxed text-gray-700">
                Sponsors{' '}
                <strong className="font-semibold">
                  {company.sponsors_portfolio.length}{' '}
                  {company.sponsors_portfolio.length === 1 ? 'entity' : 'entities'}
                </strong>{' '}
                on this list. One conversation here moves the collateral formula for all of them.
              </p>
              <div className="space-y-1">
                {company.sponsors_portfolio.map((x) => (
                  <div key={x.company_slug} className="flex items-center gap-2 text-xs">
                    <Avatar name={x.company_name} size="xs" square />
                    <span className="min-w-0 flex-1 truncate font-medium text-gray-800">
                      {x.company_name}
                    </span>
                    <span className="shrink-0 text-2xs text-gray-500 tnum">
                      Fit {x.fit_score} · Intent {x.intent_score}
                    </span>
                    <CompanyStageBadge stage={x.pipeline_stage} />
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      <section>
        <SectionTitle right={<span className="text-2xs text-gray-400">{contacted.length}</span>}>
          Contact engagement
        </SectionTitle>
        {contacted.length === 0 ? (
          <p className="text-sm text-gray-400">Nobody at this account has been contacted yet.</p>
        ) : (
          <div className="space-y-1">
            {contacted.map((e) => (
              <button
                key={e.person_id}
                onClick={() => onOpenPerson(e.person_id)}
                className="flex w-full items-center gap-3 rounded-sm px-2 py-2 text-left hover:bg-gray-50"
              >
                <Avatar name={e.name} size="sm" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-gray-800">{e.name}</div>
                  <div className="truncate text-xs text-gray-500">{e.title}</div>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  {e.deal_stage && <DealStageBadge stage={e.deal_stage} />}
                  {e.status && <StatusBadge status={e.status} />}
                </div>
              </button>
            ))}
          </div>
        )}
        {untouched.length > 0 && (
          <p className="mt-2 px-2 text-2xs text-gray-400">
            {untouched.length} more {untouched.length === 1 ? 'contact' : 'contacts'} sourced but not
            yet enrolled.
          </p>
        )}
      </section>
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div className="rounded-md border border-hairline p-2 text-center">
      <div
        className={clsx(
          'text-lg font-bold leading-none tnum',
          accent ? 'text-[#5B3F9E]' : 'text-gray-900',
        )}
      >
        {value}
      </div>
      <div className="mt-1 text-[10px] uppercase tracking-[0.04em] text-gray-500">{label}</div>
    </div>
  )
}

function PersonRow({
  person,
  onClick,
  expanded,
}: {
  person: Person
  onClick: () => void
  expanded?: boolean
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-sm px-2 py-2 text-left hover:bg-gray-50"
    >
      <Avatar name={person.name} size="md" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-gray-800">{person.name}</div>
        <div className="truncate text-xs text-gray-500">
          {person.title} · {person.role_category}
        </div>
      </div>
      {expanded && person.email && <EmailStatusBadge status={person.email_status ?? null} />}
      {!expanded && (
        <span className="text-2xs text-gray-400">{Math.round(person.confidence * 100)}%</span>
      )}
    </button>
  )
}
