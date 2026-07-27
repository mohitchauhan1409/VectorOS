import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Plus,
  Mail,
  Linkedin,
  ChevronLeft,
  ChevronDown,
  Play,
  Pause,
  Ellipsis,
  GitBranch,
  ArrowUpRight,
  Download,
  Link2,
  BarChart3,
  Archive,
  Zap,
  Hand,
  Check,
  CircleCheck,
  X,
} from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Button } from '@/components/ui/Button'
import { SearchInput } from '@/components/ui/Input'
import { Menu, MenuItem, MenuLabel, MenuSeparator } from '@/components/ui/Menu'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { Tabs, Segmented } from '@/components/ui/Tabs'
import { Badge, StatusBadge, SendModeBadge } from '@/components/ui/Badge'
import { EmptyState, KpiTile, LoadingState, ErrorState, Spinner } from '@/components/ui/Misc'
import { Avatar } from '@/components/ui/Avatar'
import { SequenceBuilder } from '@/components/SequenceBuilder'
import { PersonDrawer } from '@/components/PersonDrawer'
import { RunPipelineButton } from '@/components/RunPipelineButton'
import * as api from '@/lib/api'
import { ApiError } from '@/lib/api'
import { useAsync, useDebounced } from '@/lib/useAsync'
import { usePipeline } from '@/lib/pipeline'
import { downloadCsv, stamped, useCopy } from '@/lib/actions'
import { pct, relTime, dateOnly, dateTime } from '@/lib/format'
import type { Campaign, Channel, Enrollment } from '@/lib/types'

const ENROLLMENT_CSV = [
  { header: 'Name', value: (e: Enrollment) => e.name },
  { header: 'Title', value: (e: Enrollment) => e.title },
  { header: 'Company', value: (e: Enrollment) => e.company },
  { header: 'Channel', value: (e: Enrollment) => e.channel },
  { header: 'Email', value: (e: Enrollment) => e.email ?? '' },
  { header: 'Step', value: (e: Enrollment) => `${e.current_step}/${e.total_steps ?? ''}` },
  { header: 'Status', value: (e: Enrollment) => (e.awaiting_launch ? 'awaiting start' : e.status) },
  { header: 'Started', value: (e: Enrollment) => e.launched_at ?? '' },
  { header: 'Started by', value: (e: Enrollment) => e.launched_by ?? '' },
  { header: 'Enrolled', value: (e: Enrollment) => e.enrolled_at },
  { header: 'Last action', value: (e: Enrollment) => e.last_action_at ?? '' },
  { header: 'Next action', value: (e: Enrollment) => e.next_action_at ?? '' },
  { header: 'Replied', value: (e: Enrollment) => e.replied_at ?? '' },
]

export function CampaignsPage() {
  const [params, setParams] = useSearchParams()
  const openId = params.get('id')
  const setOpen = (id: string | null) => setParams(id ? { id } : {}, { replace: true })

  if (openId) {
    return <CampaignDetail id={openId} onBack={() => setOpen(null)} />
  }
  return <CampaignList onOpen={setOpen} />
}

function CampaignList({ onOpen }: { onOpen: (id: string) => void }) {
  const { dataVersion } = usePipeline()
  const [q, setQ] = useState('')
  const [channel, setChannel] = useState<'all' | Channel>('all')
  const debouncedQ = useDebounced(q, 250)

  const { data, loading, error, reload } = useAsync(() => api.getCampaigns(), [dataVersion])

  const all = data?.items ?? []
  const filtered = all.filter(
    (c) =>
      (channel === 'all' || c.channels.includes(channel)) &&
      c.name.toLowerCase().includes(debouncedQ.trim().toLowerCase()),
  )

  return (
    <div>
      <PageHeader
        title="Campaigns"
        subtitle="Multi-channel outreach plays designed by Pulse"
        actions={
          <>
            <Button
              variant="secondary"
              icon={<Download size={15} />}
              disabled={all.length === 0}
              onClick={() =>
                downloadCsv(stamped('vector-campaigns'), all, [
                  { header: 'Campaign', value: (c) => c.name },
                  { header: 'Status', value: (c) => c.status },
                  { header: 'Channels', value: (c) => c.channels.join(' + ') },
                  { header: 'Min ICP', value: (c) => c.icp_min_score },
                  { header: 'Enrolled', value: (c) => c.metrics?.enrolled ?? 0 },
                  { header: 'Replied', value: (c) => c.metrics?.replied ?? 0 },
                  { header: 'Meetings', value: (c) => c.metrics?.meetings ?? 0 },
                  { header: 'Deals', value: (c) => c.metrics?.deals ?? 0 },
                  { header: 'Reply rate', value: (c) => (c.metrics?.reply_rate ?? 0).toFixed(4) },
                  { header: 'Created', value: (c) => c.created_at },
                ])
              }
            >
              Export CSV
            </Button>
            <Button
              variant="primary"
              icon={<Plus size={15} />}
              disabled
              title="Campaigns are designed and built by Pulse during a pipeline run — they can't be created by hand yet."
            >
              New campaign
            </Button>
          </>
        }
      />

      <div className="mb-3 flex items-center gap-2">
        <SearchInput value={q} onChange={setQ} placeholder="Search campaigns…" className="!w-72" />
        <Segmented
          options={[
            { key: 'all', label: 'All' },
            { key: 'email', label: 'Email' },
            { key: 'linkedin', label: 'LinkedIn' },
          ]}
          value={channel}
          onChange={(k) => setChannel(k as typeof channel)}
        />
      </div>

      {loading && !data ? (
        <div className="card"><LoadingState /></div>
      ) : error && !data ? (
        <div className="card"><ErrorState message={error} onRetry={reload} /></div>
      ) : filtered.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={GitBranch}
            title={all.length === 0 ? 'No campaigns yet' : 'No campaigns found'}
            description={
              all.length === 0
                ? "Vector builds multi-channel campaigns automatically once the engine runs on the backend. They'll appear here after a pipeline run."
                : 'Try a different search or channel filter.'
            }
            action={all.length === 0 ? <RunPipelineButton /> : undefined}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {filtered.map((c) => (
            <CampaignCard key={c.id} campaign={c} onClick={() => onOpen(c.id)} />
          ))}
        </div>
      )}
    </div>
  )
}

function CampaignCard({ campaign: c, onClick }: { campaign: Campaign; onClick: () => void }) {
  const m = c.metrics
  return (
    <button
      onClick={onClick}
      className="card group p-5 text-left transition-all hover:border-hairline-strong hover:shadow-xs"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-md bg-gray-100">
            <GitBranch size={17} className="text-gray-600" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-gray-900">{c.name}</span>
              <ArrowUpRight size={14} className="text-gray-300 opacity-0 transition-opacity group-hover:opacity-100" />
            </div>
            <div className="mt-0.5 flex items-center gap-1.5">
              {c.channels.map((ch) => (
                <ChannelChip key={ch} channel={ch} />
              ))}
              <span className="text-xs text-gray-500">· created {dateOnly(c.created_at)}</span>
            </div>
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <StatusBadge status={c.status} />
          <SendModeBadge mode={c.send_mode} />
        </div>
      </div>

      <p className="mt-3 text-sm text-gray-500 line-clamp-1">{c.description}</p>

      <div className="mt-4 grid grid-cols-4 gap-3 border-t border-hairline pt-3">
        <Stat label="Enrolled" value={(m?.enrolled ?? 0).toLocaleString()} />
        <Stat
          label={c.send_mode === 'manual' ? 'Awaiting start' : 'Replied'}
          value={(c.send_mode === 'manual'
            ? (m?.awaiting_launch ?? 0)
            : (m?.replied ?? 0)
          ).toLocaleString()}
        />
        <Stat label="Meetings" value={(m?.meetings ?? 0).toLocaleString()} />
        <Stat label="Reply rate" value={pct(m?.reply_rate ?? 0, 0)} />
      </div>
    </button>
  )
}

function ChannelChip({ channel }: { channel: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-xs bg-gray-100 px-1.5 py-0.5 text-2xs font-medium text-gray-600">
      {channel === 'email' ? <Mail size={11} /> : <Linkedin size={11} />}
      <span className="capitalize">{channel}</span>
    </span>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-sm font-semibold text-gray-900 tnum">{value}</div>
      <div className="text-2xs uppercase tracking-[0.04em] text-gray-500">{label}</div>
    </div>
  )
}

function CampaignDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const { dataVersion } = usePipeline()
  const { copy } = useCopy()
  const [tab, setTab] = useState('steps')
  const [channel, setChannel] = useState<Channel>('email')
  const [openPersonId, setOpenPersonId] = useState<string | null>(null)

  // status + sending-mode changes
  const [status, setStatus] = useState<string | null>(null)
  const [statusBusy, setStatusBusy] = useState(false)
  const [statusNotice, setStatusNotice] = useState<string | null>(null)
  const [sendMode, setSendMode] = useState<string | null>(null)
  const [modeBusy, setModeBusy] = useState(false)
  // Bumped after a launch so the enrolled table + metrics refetch.
  const [launchVersion, setLaunchVersion] = useState(0)

  const { data: campaign, loading, error, reload } = useAsync(
    () => api.getCampaign(id),
    [id, dataVersion, launchVersion],
  )

  if (loading && !campaign) {
    return (
      <div>
        <BackLink onBack={onBack} />
        <LoadingState />
      </div>
    )
  }
  if (error && !campaign) {
    return (
      <div>
        <BackLink onBack={onBack} />
        <ErrorState message={error} onRetry={reload} />
      </div>
    )
  }
  if (!campaign) return null

  const m = campaign.metrics
  const sequences = campaign.sequences ?? []
  const channels = campaign.channels.length ? campaign.channels : sequences.map((s) => s.channel)
  const activeChannel = channels.includes(channel) ? channel : (channels[0] as Channel)
  const activeSequence = sequences.find((s) => s.channel === activeChannel) ?? sequences[0]
  const effectiveStatus = status ?? campaign.status
  const effectiveMode = sendMode ?? campaign.send_mode
  const isManual = effectiveMode === 'manual'

  const changeStatus = async (next: string) => {
    setStatusBusy(true)
    setStatusNotice(null)
    try {
      const updated = await api.patchCampaignStatus(id, next)
      setStatus(updated.status)
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) setStatusNotice('Demo workspace is read-only')
      else setStatusNotice(err instanceof Error ? err.message : 'Could not update status.')
    } finally {
      setStatusBusy(false)
    }
  }

  const changeSendMode = async (next: string) => {
    if (next === effectiveMode) return
    setModeBusy(true)
    setStatusNotice(null)
    setSendMode(next) // optimistic
    try {
      const updated = await api.patchSendMode(id, next)
      setSendMode(updated.send_mode)
      setLaunchVersion((v) => v + 1)
    } catch (err) {
      setSendMode(effectiveMode)
      setStatusNotice(err instanceof Error ? err.message : 'Could not change sending mode.')
    } finally {
      setModeBusy(false)
    }
  }

  return (
    <div>
      <BackLink onBack={onBack} />

      <div className="mb-4 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-md bg-gray-100">
            <GitBranch size={20} className="text-gray-600" />
          </span>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-bold tracking-[-0.01em] text-gray-900">{campaign.name}</h1>
              <StatusBadge status={effectiveStatus} />
              <SendModeBadge mode={effectiveMode} />
            </div>
            <p className="mt-0.5 text-sm text-gray-500">
              {channels.join(' · ')} · {sequences.reduce((n, s) => n + s.steps.length, 0)} steps ·{' '}
              {(m?.enrolled ?? 0).toLocaleString()} enrolled · min ICP {campaign.icp_min_score}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="flex items-center gap-2">
            <SendModeControl
              mode={effectiveMode}
              busy={modeBusy}
              awaiting={m?.awaiting_launch ?? 0}
              onChange={changeSendMode}
            />
            {effectiveStatus === 'active' ? (
              <Button
                variant="secondary"
                icon={statusBusy ? <Spinner size={14} /> : <Pause size={15} />}
                disabled={statusBusy}
                onClick={() => changeStatus('paused')}
              >
                Pause
              </Button>
            ) : (
              <Button
                variant="primary"
                icon={statusBusy ? <Spinner size={14} /> : <Play size={15} />}
                disabled={statusBusy}
                onClick={() => changeStatus('active')}
              >
                Activate
              </Button>
            )}
            <Menu
              trigger={() => (
                <Button variant="ghost" size="md" className="!w-8 !px-0" aria-label="More actions">
                  <Ellipsis size={16} />
                </Button>
              )}
            >
              {(close) => (
                <>
                  <MenuLabel>Campaign</MenuLabel>
                  <MenuItem
                    icon={<Link2 size={14} />}
                    onClick={() => {
                      void copy(`${window.location.origin}/campaigns?id=${id}`, 'link')
                      close()
                    }}
                  >
                    Copy link
                  </MenuItem>
                  <MenuItem
                    icon={<BarChart3 size={14} />}
                    onClick={() => {
                      close()
                      setTab('analytics')
                    }}
                  >
                    View analytics
                  </MenuItem>
                  <MenuItem
                    icon={<Download size={14} />}
                    onClick={() => {
                      void api
                        .getCampaignEnrollments(id)
                        .then((r) =>
                          downloadCsv(stamped(`${campaign.name}-enrollments`), r.items, ENROLLMENT_CSV),
                        )
                      close()
                    }}
                  >
                    Export enrollments
                  </MenuItem>
                  <MenuSeparator />
                  <MenuItem
                    icon={<Archive size={14} />}
                    disabled={statusBusy || effectiveStatus === 'archived'}
                    onClick={() => {
                      close()
                      void changeStatus('archived')
                    }}
                  >
                    Archive campaign
                  </MenuItem>
                </>
              )}
            </Menu>
          </div>
          {statusNotice && <span className="text-xs text-warning-text">{statusNotice}</span>}
        </div>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiTile label="Enrolled" value={(m?.enrolled ?? 0).toLocaleString()} />
        <KpiTile label="Replied" value={(m?.replied ?? 0).toLocaleString()} />
        <KpiTile label="Meetings" value={(m?.meetings ?? 0).toLocaleString()} />
        <KpiTile label="In deal" value={(m?.deals ?? 0).toLocaleString()} />
      </div>

      {isManual && (m?.awaiting_launch ?? 0) > 0 && (
        <button
          onClick={() => setTab('enrolled')}
          className="mb-4 flex w-full items-center gap-2.5 rounded-md border border-[#E5C98F] bg-warning-bg px-4 py-3 text-left transition-colors hover:border-[#D4B473]"
        >
          <Hand size={15} className="shrink-0 text-warning-text" />
          <span className="flex-1 text-sm text-warning-text">
            <strong className="font-semibold">
              {m!.awaiting_launch} {m!.awaiting_launch === 1 ? 'person is' : 'people are'} awaiting start
            </strong>{' '}
            — this campaign is in manual mode, so nothing sends until you release them.
          </span>
          <span className="shrink-0 text-2xs font-medium text-warning-text">Review →</span>
        </button>
      )}

      <div className="mb-4">
        <Tabs
          tabs={[
            { key: 'steps', label: 'Steps' },
            { key: 'enrolled', label: 'Enrolled', count: m?.enrolled },
            { key: 'analytics', label: 'Analytics' },
          ]}
          active={tab}
          onChange={setTab}
        />
      </div>

      {tab === 'steps' && channels.length > 1 && (
        <div className="mb-4">
          <Segmented
            options={channels.map((ch) => ({ key: ch, label: ch === 'email' ? 'Email' : 'LinkedIn' }))}
            value={activeChannel}
            onChange={(k) => setChannel(k as Channel)}
          />
        </div>
      )}

      {tab === 'steps' && (
        <div className="max-w-3xl">
          {activeSequence ? (
            <SequenceBuilder sequence={activeSequence} />
          ) : (
            <p className="text-sm text-gray-400">No sequence configured for this channel.</p>
          )}
        </div>
      )}

      {tab === 'enrolled' && (
        <EnrolledTable
          campaignId={id}
          isManual={isManual}
          version={launchVersion}
          onOpenPerson={setOpenPersonId}
          onLaunched={() => setLaunchVersion((v) => v + 1)}
        />
      )}

      {tab === 'analytics' && m && <CampaignAnalytics metrics={m} />}

      <PersonDrawer personId={openPersonId} onClose={() => setOpenPersonId(null)} />
    </div>
  )
}

/**
 * Sending mode picker. Switching to autonomous is the only irreversible-feeling
 * direction — it releases every held person and every future one without asking
 * again — so it takes a second, explicit confirmation.
 */
function SendModeControl({
  mode,
  busy,
  awaiting,
  onChange,
}: {
  mode: string
  busy: boolean
  awaiting: number
  onChange: (next: string) => void
}) {
  const [confirming, setConfirming] = useState(false)
  const autonomous = mode === 'autonomous'

  return (
    <>
      <Menu
        width={300}
        trigger={() => (
          <Button
            variant="secondary"
            icon={busy ? <Spinner size={14} /> : autonomous ? <Zap size={15} /> : <Hand size={15} />}
            iconRight={<ChevronDown size={14} className="text-gray-400" />}
            disabled={busy}
            title="Controls whether the first touch sends automatically"
          >
            Sending: {autonomous ? 'Autonomous' : 'Manual'}
          </Button>
        )}
      >
        {(close) => (
          <>
            <MenuLabel>Sending mode</MenuLabel>
            <ModeOption
              icon={<Hand size={14} />}
              label="Manual"
              description="Hold every first touch. You release each person yourself from the Enrolled tab."
              selected={!autonomous}
              onClick={() => {
                close()
                onChange('manual')
              }}
            />
            <ModeOption
              icon={<Zap size={14} />}
              label="Autonomous"
              description="Vector sends the first touch as soon as it's due, for everyone."
              selected={autonomous}
              onClick={() => {
                close()
                if (!autonomous) setConfirming(true)
              }}
            />
            <div className="border-t border-hairline px-2.5 py-2 text-2xs leading-relaxed text-gray-400">
              Either way, follow-up steps after the first touch always run on the sequence
              schedule.
            </div>
          </>
        )}
      </Menu>

      <ConfirmDialog
        open={confirming}
        title="Switch to autonomous sending?"
        confirmLabel="Yes, send autonomously"
        cancelLabel="Keep manual"
        busy={busy}
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false)
          onChange('autonomous')
        }}
      >
        <p>
          Vector will start sending the first touch{' '}
          <strong className="font-semibold text-gray-900">without asking you again</strong> — to
          {awaiting > 0 ? (
            <>
              {' '}
              the{' '}
              <strong className="font-semibold text-gray-900">
                {awaiting} {awaiting === 1 ? 'person' : 'people'}
              </strong>{' '}
              currently held for approval, and to
            </>
          ) : (
            ''
          )}{' '}
          everyone enrolled in this campaign from now on.
        </p>
        <p className="mt-2">
          Real emails and LinkedIn requests go out on the next engine cycle, subject to the send
          window and daily caps. You can switch back to manual at any time, but anything already
          sent can't be recalled.
        </p>
      </ConfirmDialog>
    </>
  )
}

function ModeOption({
  icon,
  label,
  description,
  selected,
  onClick,
}: {
  icon: React.ReactNode
  label: string
  description: string
  selected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-start gap-2.5 rounded-sm px-2.5 py-2 text-left hover:bg-gray-100"
    >
      <span className="mt-0.5 shrink-0 text-gray-400">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5">
          <span className="text-sm font-medium text-gray-800">{label}</span>
          {selected && <Check size={13} className="text-brand-600" />}
        </span>
        <span className="mt-0.5 block text-2xs leading-snug text-gray-500">{description}</span>
      </span>
    </button>
  )
}

function BackLink({ onBack }: { onBack: () => void }) {
  return (
    <button onClick={onBack} className="mb-3 inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800">
      <ChevronLeft size={15} /> Campaigns
    </button>
  )
}

/**
 * Everyone enrolled in the campaign, across both channels. In manual sending
 * mode each held person gets a Start button that releases their first touch.
 */
function EnrolledTable({
  campaignId,
  isManual,
  version,
  onOpenPerson,
  onLaunched,
}: {
  campaignId: string
  isManual: boolean
  version: number
  onOpenPerson: (id: string) => void
  onLaunched: () => void
}) {
  const [channel, setChannel] = useState<'all' | Channel>('all')
  const [only, setOnly] = useState<'all' | 'held' | 'live'>('all')
  const [q, setQ] = useState('')
  const debouncedQ = useDebounced(q, 250)
  const [rows, setRows] = useState<Enrollment[]>([])
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set())
  const [bulkBusy, setBulkBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const { data, loading, error, reload } = useAsync(
    () =>
      api.getCampaignEnrollments(campaignId, {
        channel: channel === 'all' ? undefined : channel,
        q: debouncedQ.trim() || undefined,
        held: only === 'all' ? undefined : only === 'held',
      }),
    [campaignId, channel, only, debouncedQ, version],
  )

  useEffect(() => setRows(data?.items ?? []), [data])

  const held = rows.filter((e) => e.awaiting_launch)

  const launch = async (ids: number[], bulk = false) => {
    setNotice(null)
    const idSet = new Set(ids.map(String))
    if (bulk) setBulkBusy(true)
    else setBusyIds((s) => new Set([...s, ...idSet]))
    // Optimistic: drop the hold immediately.
    const before = rows
    setRows(rows.map((e) => (idSet.has(e.id) ? { ...e, awaiting_launch: false } : e)))
    try {
      const res = await api.launchEnrollments(campaignId, { enrollment_ids: ids })
      setNotice(
        res.released === 0
          ? 'Nothing to release — those first touches already went out.'
          : `Released ${res.released} first ${res.released === 1 ? 'touch' : 'touches'}.`,
      )
      onLaunched()
    } catch (err) {
      setRows(before)
      setNotice(err instanceof Error ? err.message : 'Could not start the campaign.')
    } finally {
      setBulkBusy(false)
      setBusyIds((s) => {
        const next = new Set(s)
        idSet.forEach((i) => next.delete(i))
        return next
      })
    }
  }

  const launchAll = async () => {
    setNotice(null)
    setBulkBusy(true)
    const before = rows
    setRows(rows.map((e) => ({ ...e, awaiting_launch: false })))
    try {
      const res = await api.launchEnrollments(campaignId, {
        all: true,
        channel: channel === 'all' ? undefined : channel,
      })
      setNotice(`Released ${res.released} first ${res.released === 1 ? 'touch' : 'touches'}.`)
      onLaunched()
    } catch (err) {
      setRows(before)
      setNotice(err instanceof Error ? err.message : 'Could not start the campaign.')
    } finally {
      setBulkBusy(false)
    }
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <SearchInput value={q} onChange={setQ} placeholder="Search enrolled people…" className="!w-64" />
        <Segmented
          options={[
            { key: 'all', label: 'All channels' },
            { key: 'email', label: 'Email' },
            { key: 'linkedin', label: 'LinkedIn' },
          ]}
          value={channel}
          onChange={(k) => setChannel(k as typeof channel)}
        />
        {isManual && (
          <Segmented
            options={[
              { key: 'all', label: 'All' },
              { key: 'held', label: 'Awaiting start' },
              { key: 'live', label: 'Started' },
            ]}
            value={only}
            onChange={(k) => setOnly(k as typeof only)}
          />
        )}
        {loading && data && <Spinner size={14} className="text-gray-400" />}
        <div className="flex-1" />
        {isManual && held.length > 0 && (
          <Button
            variant="primary"
            size="md"
            icon={bulkBusy ? <Spinner size={14} /> : <Play size={14} />}
            disabled={bulkBusy}
            onClick={launchAll}
          >
            Start all {held.length} held
          </Button>
        )}
      </div>

      {notice && (
        <div className="mb-3 flex items-center gap-2 rounded-md border border-hairline bg-sunken px-3 py-2 text-sm text-gray-700">
          <CircleCheck size={15} className="shrink-0 text-success" />
          <span className="flex-1">{notice}</span>
          <button onClick={() => setNotice(null)} aria-label="Dismiss" className="text-gray-400 hover:text-gray-700">
            <X size={14} />
          </button>
        </div>
      )}

      <div className="card overflow-hidden">
        {loading && !data ? (
          <LoadingState />
        ) : error && !data ? (
          <ErrorState message={error} onRetry={reload} />
        ) : rows.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-gray-400">
            {q.trim() || only !== 'all' || channel !== 'all'
              ? 'No enrolled people match these filters.'
              : 'No one is enrolled in this campaign yet.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-hairline bg-gray-50 text-2xs font-semibold uppercase tracking-[0.02em] text-gray-500">
                  <th className="px-4 py-2.5">Contact</th>
                  <th className="px-4 py-2.5">Company</th>
                  <th className="px-4 py-2.5">Channel</th>
                  <th className="px-4 py-2.5">Step</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Next action</th>
                  <th className="px-4 py-2.5 text-right">{isManual ? 'Start' : ''}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((e) => (
                  <tr
                    key={e.id}
                    onClick={() => onOpenPerson(e.person_id)}
                    className="h-14 cursor-pointer border-b border-hairline hover:bg-gray-50"
                  >
                    <td className="px-4">
                      <div className="flex items-center gap-2.5">
                        <Avatar name={e.name} size="sm" />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-gray-800">{e.name}</div>
                          <div className="truncate text-xs text-gray-500">{e.title}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 text-sm text-gray-700">{e.company}</td>
                    <td className="px-4">
                      <span className="inline-flex items-center gap-1.5 text-xs capitalize text-gray-600">
                        {e.channel === 'email' ? (
                          <Mail size={13} className="text-gray-400" />
                        ) : (
                          <Linkedin size={13} className="text-gray-400" />
                        )}
                        {e.channel}
                      </span>
                    </td>
                    <td className="px-4 text-sm text-gray-600 tnum">
                      {e.current_step} / {e.total_steps ?? '—'}
                    </td>
                    <td className="px-4">
                      {e.awaiting_launch ? (
                        <Badge tone="warning" dot>
                          awaiting start
                        </Badge>
                      ) : (
                        <StatusBadge status={e.status} />
                      )}
                    </td>
                    <td className="px-4 text-xs text-gray-500">
                      {e.awaiting_launch
                        ? 'Held'
                        : e.next_action_at
                          ? relTime(e.next_action_at)
                          : relTime(e.last_action_at)}
                    </td>
                    <td className="px-4 text-right" onClick={(ev) => ev.stopPropagation()}>
                      {e.awaiting_launch ? (
                        <Button
                          variant="primary"
                          size="sm"
                          icon={busyIds.has(e.id) ? <Spinner size={13} /> : <Play size={13} />}
                          disabled={busyIds.has(e.id) || bulkBusy}
                          onClick={() => launch([Number(e.id)])}
                          title={`Send the first ${e.channel === 'email' ? 'email' : 'connection request'} to ${e.name}`}
                        >
                          Start
                        </Button>
                      ) : e.launched_at ? (
                        <span
                          className="text-2xs text-gray-400"
                          title={
                            e.launched_by
                              ? `Released by ${e.launched_by} · ${dateTime(e.launched_at)}`
                              : undefined
                          }
                        >
                          Started
                        </span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {rows.length > 0 && (
          <div className="flex h-12 items-center justify-between border-t border-hairline px-4 text-sm text-gray-500">
            <span className="tnum">
              Showing {rows.length} of {data?.total ?? rows.length}
              {isManual && held.length > 0 && ` · ${held.length} awaiting start`}
            </span>
            <Button
              variant="ghost"
              size="sm"
              icon={<Download size={14} />}
              onClick={() => downloadCsv(stamped('enrollments'), rows, ENROLLMENT_CSV)}
            >
              Export
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

function CampaignAnalytics({ metrics }: { metrics: NonNullable<Campaign['metrics']> }) {
  const funnel = [
    { label: 'Enrolled', value: metrics.enrolled },
    { label: 'Active', value: metrics.active },
    { label: 'Replied', value: metrics.replied },
    { label: 'Meeting', value: metrics.meetings },
    { label: 'Booked', value: metrics.booked },
  ]
  const max = Math.max(...funnel.map((f) => f.value), 1)
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="card p-5">
        <h3 className="mb-4 text-sm font-semibold text-gray-800">Funnel</h3>
        <div className="space-y-3">
          {funnel.map((f) => (
            <div key={f.label}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-gray-600">{f.label}</span>
                <span className="font-medium text-gray-800 tnum">{f.value.toLocaleString()}</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
                <div className="h-full rounded-full bg-brand-600" style={{ width: `${(f.value / max) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="card p-5">
        <h3 className="mb-4 text-sm font-semibold text-gray-800">Status breakdown</h3>
        <div className="space-y-2">
          {Object.entries(metrics.by_status)
            .sort((a, b) => b[1] - a[1])
            .map(([s, count]) => (
              <div key={s} className="flex items-center justify-between">
                <StatusBadge status={s} />
                <span className="text-sm font-medium text-gray-800 tnum">{count}</span>
              </div>
            ))}
        </div>
      </div>
    </div>
  )
}
