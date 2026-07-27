import { useEffect, useState } from 'react'
import {
  X,
  Maximize2,
  Minimize2,
  Ellipsis,
  Mail,
  Linkedin,
  Copy,
  Check,
  ArrowUpRight,
  ArrowRight,
  MapPin,
  ChevronLeft,
  ChevronRight,
  Handshake,
  Building2,
  Link2,
  Trash2,
  Download,
  CalendarClock,
} from 'lucide-react'
import { Drawer } from '@/components/ui/Drawer'
import { Avatar } from '@/components/ui/Avatar'
import { Button, IconButton } from '@/components/ui/Button'
import { Menu, MenuItem, MenuLabel, MenuSeparator } from '@/components/ui/Menu'
import { Tabs } from '@/components/ui/Tabs'
import {
  Badge,
  StatusBadge,
  EmailStatusBadge,
  SignalBadge,
  TierBadge,
  ReplyClassBadge,
  DealStageBadge,
  HealthBadge,
} from '@/components/ui/Badge'
import { KeyValue, SectionTitle, Meter, LoadingState, ErrorState } from '@/components/ui/Misc'
import { SignalIcon } from '@/components/ui/icons'
import { Timeline } from '@/components/Timeline'
import { DealPanel } from '@/components/DealPanel'
import { MeetingsPanel } from '@/components/MeetingsPanel'
import * as api from '@/lib/api'
import { useAsync } from '@/lib/useAsync'
import {
  addNote,
  deleteNote,
  downloadCsv,
  getNotes,
  stamped,
  useCopy,
  type Note,
} from '@/lib/actions'
import { relTime, dateTime, dateOnly, money } from '@/lib/format'

export function PersonDrawer({
  personId,
  onClose,
  onNav,
  onOpenCompany,
}: {
  personId: string | null
  onClose: () => void
  onNav?: (dir: -1 | 1) => void
  onOpenCompany?: (slug: string) => void
}) {
  const [tab, setTab] = useState('overview')
  const [expanded, setExpanded] = useState(false)
  const [meetingCount, setMeetingCount] = useState(0)
  const { copy, copied } = useCopy()
  const { data: person, loading, error, reload } = useAsync(
    async () => (personId ? api.getPerson(personId) : null),
    [personId],
  )

  // Reset to Overview whenever a different contact is opened, so a tab that
  // doesn't exist on the next person (e.g. Deal) can't leave the body blank.
  useEffect(() => setTab('overview'), [personId])

  // Mirrors the panel's optimistic list so the tab badge updates instantly.
  useEffect(() => setMeetingCount(person?.meetings?.length ?? 0), [person])

  if (!personId) return null

  const company = person?.company ?? null
  const enrolls = person?.enrollments ?? []
  const events = person?.timeline ?? []
  const thread = person?.thread ?? []
  const deal = person?.deal ?? null
  const meetings = person?.meetings ?? []
  const status = enrolls[0]?.status ?? 'active'
  // Soonest upcoming meeting — surfaced on Overview so it's never buried.
  const nextMeeting = meetings
    .filter((m) => m.status === 'scheduled')
    .sort((a, b) => a.occurred_at.localeCompare(b.occurred_at))[0]

  return (
    <Drawer open={!!personId} onClose={onClose} width={expanded ? 900 : 620}>
      {loading || !person ? (
        error ? (
          <div className="flex flex-1 items-center justify-center">
            <ErrorState message={error} onRetry={reload} />
          </div>
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <LoadingState label="Loading contact…" />
          </div>
        )
      ) : (
        <>
          {/* Header */}
          <div className="flex items-start gap-3 border-b border-hairline px-6 py-4">
            <Avatar name={person.name} size="xl" />
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-xl font-semibold text-gray-900">{person.name}</h2>
              <p className="truncate text-sm text-gray-500">
                {person.title}
                {company ? ` · ${company.company_name}` : ''}
              </p>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                {enrolls.length > 0 && <StatusBadge status={status} />}
                {deal && <DealStageBadge stage={deal.stage} />}
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
                    {person.email && (
                      <MenuItem
                        icon={<Mail size={14} />}
                        onClick={() => {
                          void copy(person.email!, 'email')
                          close()
                        }}
                      >
                        Email address
                      </MenuItem>
                    )}
                    {person.linkedin_url && (
                      <MenuItem
                        icon={<Linkedin size={14} />}
                        onClick={() => {
                          void copy(person.linkedin_url!, 'li')
                          close()
                        }}
                      >
                        LinkedIn URL
                      </MenuItem>
                    )}
                    <MenuItem
                      icon={<Link2 size={14} />}
                      onClick={() => {
                        void copy(`${window.location.origin}/people?id=${person.id}`, 'link')
                        close()
                      }}
                    >
                      Link to contact
                    </MenuItem>
                    <MenuSeparator />
                    <MenuItem
                      icon={<Download size={14} />}
                      onClick={() => {
                        downloadCsv(
                          stamped(`${person.name.toLowerCase().replace(/\s+/g, '-')}-thread`),
                          thread,
                          [
                            { header: 'Date', value: (m) => m.at },
                            { header: 'Channel', value: (m) => m.channel },
                            { header: 'Direction', value: (m) => m.direction },
                            { header: 'Step', value: (m) => m.step_name },
                            { header: 'Subject', value: (m) => m.subject ?? '' },
                            { header: 'Body', value: (m) => m.body },
                            { header: 'Reply class', value: (m) => m.reply_class ?? '' },
                          ],
                        )
                        close()
                      }}
                      disabled={thread.length === 0}
                    >
                      Export thread (CSV)
                    </MenuItem>
                    {company && (
                      <MenuItem
                        icon={<Building2 size={14} />}
                        onClick={() => {
                          close()
                          onOpenCompany?.(company.company_slug)
                        }}
                      >
                        Open company
                      </MenuItem>
                    )}
                  </>
                )}
              </Menu>
              <IconButton aria-label="Close" onClick={onClose}><X size={16} /></IconButton>
            </div>
          </div>

          {/* Action row */}
          <div className="flex items-center gap-2 border-b border-hairline px-6 py-3">
            {person.email ? (
              <Button
                variant="primary"
                size="sm"
                icon={<Mail size={14} />}
                onClick={() => {
                  window.location.href = `mailto:${person.email}`
                }}
              >
                Email
              </Button>
            ) : (
              <Button variant="primary" size="sm" icon={<Mail size={14} />} disabled title="No email found for this contact">
                Email
              </Button>
            )}
            <Button
              variant="secondary"
              size="sm"
              icon={copied === 'email' ? <Check size={14} /> : <Copy size={14} />}
              disabled={!person.email}
              onClick={() => person.email && void copy(person.email, 'email')}
            >
              {copied === 'email' ? 'Copied' : 'Copy email'}
            </Button>
            <div className="flex-1" />
            {person.linkedin_url && (
              <IconButton
                aria-label="Open LinkedIn profile"
                title="Open LinkedIn profile"
                size="sm"
                onClick={() => window.open(person.linkedin_url!, '_blank', 'noopener')}
              >
                <Linkedin size={15} />
              </IconButton>
            )}
          </div>

          {/* Tabs */}
          <div className="px-6">
            <Tabs
              tabs={[
                { key: 'overview', label: 'Overview' },
                { key: 'activity', label: 'Activity', count: events.length },
                { key: 'emails', label: 'Emails', count: thread.length },
                // Only for contacts past the first meeting — powered by Closer.
                ...(deal ? [{ key: 'deal', label: 'Deal', count: deal.open_step_count }] : []),
                { key: 'meetings', label: 'Meetings', count: meetingCount },
                { key: 'notes', label: 'Notes' },
              ]}
              active={tab}
              onChange={setTab}
            />
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {tab === 'overview' && (
              <div className="space-y-6">
                {deal && (
                  <button
                    onClick={() => setTab('deal')}
                    className="group w-full rounded-md border border-[#DCD2F0] bg-[#F8F5FE] p-3 text-left transition-colors hover:border-[#C4B3E6]"
                  >
                    <div className="flex items-center gap-2">
                      <Handshake size={15} className="text-[#5B3F9E]" />
                      <span className="text-sm font-semibold text-gray-900">In deal</span>
                      <DealStageBadge stage={deal.stage} />
                      <HealthBadge health={deal.health} />
                      <ArrowRight
                        size={14}
                        className="ml-auto text-gray-400 transition-transform group-hover:translate-x-0.5"
                      />
                    </div>
                    <div className="mt-2 flex items-center gap-4 text-xs text-gray-600">
                      <span className="font-semibold text-gray-900 tnum">{money(deal.value_usd)}</span>
                      <span className="tnum">{deal.probability}% win</span>
                      <span>{deal.open_step_count} open steps</span>
                    </div>
                  </button>
                )}

                {nextMeeting && (
                  <button
                    onClick={() => setTab('meetings')}
                    className="group flex w-full items-center gap-2.5 rounded-md border border-brand-200 bg-brand-50/50 p-3 text-left transition-colors hover:border-brand-300"
                  >
                    <CalendarClock size={15} className="shrink-0 text-brand-700" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold text-gray-900">
                        {nextMeeting.title}
                      </div>
                      <div className="text-xs text-gray-600">
                        {dateTime(nextMeeting.occurred_at)} · {nextMeeting.duration_min} min
                      </div>
                    </div>
                    <span className="shrink-0 text-2xs font-medium text-brand-700">
                      {relTime(nextMeeting.occurred_at)}
                    </span>
                    <ArrowRight
                      size={14}
                      className="shrink-0 text-gray-400 transition-transform group-hover:translate-x-0.5"
                    />
                  </button>
                )}

                <section>
                  <SectionTitle>Contact</SectionTitle>
                  <div className="divide-y divide-hairline">
                    <KeyValue label="Email">
                      {person.email ? (
                        <div className="flex items-center gap-2">
                          <span className="truncate">{person.email}</span>
                          <EmailStatusBadge status={person.email_status ?? null} />
                          <button
                            aria-label="Copy email address"
                            title="Copy email address"
                            onClick={() => void copy(person.email!, 'kv-email')}
                            className="shrink-0 text-gray-400 hover:text-gray-700"
                          >
                            {copied === 'kv-email' ? (
                              <Check size={13} className="text-success" />
                            ) : (
                              <Copy size={13} />
                            )}
                          </button>
                        </div>
                      ) : (
                        <span className="text-gray-400">Not found</span>
                      )}
                    </KeyValue>
                    {person.email_source && (
                      <KeyValue label="Source">
                        <span className="font-mono text-xs text-gray-600">{person.email_source}</span>
                      </KeyValue>
                    )}
                    <KeyValue label="LinkedIn">
                      {person.linkedin_url ? (
                        <a
                          href={person.linkedin_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-brand-600 hover:underline"
                        >
                          View profile <ArrowUpRight size={13} />
                        </a>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </KeyValue>
                    <KeyValue label="Role">
                      <Badge tone="neutral">{person.role_category}</Badge>
                    </KeyValue>
                    <KeyValue label="Confidence">
                      <span className="tnum">{Math.round(person.confidence * 100)}%</span>
                    </KeyValue>
                    {(person.city || person.country) && (
                      <KeyValue label="Location">
                        <span className="inline-flex items-center gap-1">
                          <MapPin size={13} className="text-gray-400" />
                          {[person.city, person.country].filter(Boolean).join(', ')}
                        </span>
                      </KeyValue>
                    )}
                  </div>
                </section>

                {company && (
                  <section>
                    <SectionTitle
                      right={
                        <button
                          onClick={() => onOpenCompany?.(company.company_slug)}
                          className="inline-flex items-center gap-1 text-2xs font-medium text-brand-600 hover:underline"
                        >
                          Open <ArrowUpRight size={12} />
                        </button>
                      }
                    >
                      Company
                    </SectionTitle>
                    <div className="rounded-md border border-hairline p-3">
                      <div className="flex items-center gap-2.5">
                        <Avatar name={company.company_name} size="md" square />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium text-gray-800">
                            {company.company_name}
                          </div>
                          <div className="truncate text-xs text-gray-500">{company.industry}</div>
                        </div>
                        <TierBadge tier={company.icp.tier} />
                      </div>
                      <div className="mt-3 flex items-center justify-between">
                        <SignalBadge signal={company.signal_type} icon={<SignalIcon signal={company.signal_type} />} />
                        <Meter value={company.icp.score} tier={company.icp.tier} />
                      </div>
                    </div>
                  </section>
                )}

                <section>
                  <SectionTitle>Sequences</SectionTitle>
                  {enrolls.length === 0 ? (
                    <p className="text-sm text-gray-400">Not enrolled in any sequence.</p>
                  ) : (
                    <div className="space-y-2">
                      {enrolls.map((e) => {
                        const total = e.total_steps ?? 0
                        return (
                          <div key={e.id} className="rounded-md border border-hairline p-3">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                {e.channel === 'email' ? (
                                  <Mail size={14} className="text-gray-500" />
                                ) : (
                                  <Linkedin size={14} className="text-gray-500" />
                                )}
                                <span className="text-sm font-medium text-gray-800">{e.campaign_name}</span>
                              </div>
                              <StatusBadge status={e.status} />
                            </div>
                            <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
                              <span>
                                Step {e.current_step} of {total}
                              </span>
                              <span>
                                {e.next_action_at
                                  ? `Next ${relTime(e.next_action_at)}`
                                  : `Last ${relTime(e.last_action_at)}`}
                              </span>
                            </div>
                            <div className="mt-2 flex gap-1">
                              {Array.from({ length: total }).map((_, i) => (
                                <div
                                  key={i}
                                  className="h-1 flex-1 rounded-full"
                                  style={{
                                    background: i < e.current_step ? '#33409B' : '#E5E9F0',
                                  }}
                                />
                              ))}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </section>

                <section>
                  <SectionTitle>Recent activity</SectionTitle>
                  <Timeline events={events.slice(0, 5)} />
                </section>
              </div>
            )}

            {tab === 'activity' && <Timeline events={events} />}

            {tab === 'emails' && (
              <div className="space-y-3">
                {thread.length === 0 ? (
                  <p className="text-sm text-gray-400">No messages sent yet.</p>
                ) : (
                  thread.map((m) => (
                    <div
                      key={m.id}
                      className={
                        m.direction === 'inbound'
                          ? 'rounded-md border border-brand-200 bg-brand-50 p-3'
                          : 'rounded-md border border-hairline bg-white p-3'
                      }
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-xs font-medium text-gray-600">
                          {m.channel === 'email' ? <Mail size={13} /> : <Linkedin size={13} />}
                          {m.direction === 'inbound' ? 'Reply' : m.step_name}
                        </div>
                        <span className="text-2xs text-gray-400" title={dateTime(m.at)}>
                          {relTime(m.at)}
                        </span>
                      </div>
                      {m.subject && (
                        <div className="mt-1.5 text-sm font-medium text-gray-800">{m.subject}</div>
                      )}
                      <p className="mt-1 whitespace-pre-line text-sm text-gray-600 line-clamp-4">
                        {m.body}
                      </p>
                      {m.reply_class && (
                        <div className="mt-2">
                          <ReplyClassBadge rc={m.reply_class} />
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {tab === 'deal' && deal && (
              <DealPanel deal={deal} onOpenMeetings={() => setTab('meetings')} />
            )}

            {tab === 'meetings' && (
              <MeetingsPanel
                personId={person.id}
                personName={person.name}
                initial={meetings}
                onCountChange={(list) => setMeetingCount(list.length)}
              />
            )}

            {tab === 'notes' && <NotesTab personId={person.id} />}
          </div>

          {/* Footer nav */}
          {onNav ? (
            <div className="flex items-center justify-between border-t border-hairline px-6 py-2.5">
              <span className="text-2xs text-gray-400">
                Discovered {dateOnly(events[events.length - 1]?.created_at ?? null)}
              </span>
              <div className="flex items-center gap-1">
                <IconButton size="sm" aria-label="Previous" onClick={() => onNav(-1)}>
                  <ChevronLeft size={16} />
                </IconButton>
                <IconButton size="sm" aria-label="Next" onClick={() => onNav(1)}>
                  <ChevronRight size={16} />
                </IconButton>
              </div>
            </div>
          ) : null}
        </>
      )}
    </Drawer>
  )
}

/**
 * Notes are stored in this browser only — the Vector API is display-only, so
 * there is nowhere to persist them server-side yet.
 */
function NotesTab({ personId }: { personId: string }) {
  const [notes, setNotes] = useState<Note[]>(() => getNotes(personId))
  const [draft, setDraft] = useState('')

  useEffect(() => {
    setNotes(getNotes(personId))
    setDraft('')
  }, [personId])

  const save = () => {
    const body = draft.trim()
    if (!body) return
    setNotes(addNote(personId, body))
    setDraft('')
  }

  return (
    <div className="py-1">
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') save()
        }}
        placeholder="Add a note about this contact…"
        className="h-28 w-full resize-none rounded-md border border-hairline-strong p-3 text-sm placeholder:text-gray-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/35"
      />
      <div className="mt-2 flex items-center justify-between">
        <span className="text-2xs text-gray-400">Saved in this browser · ⌘↵ to save</span>
        <Button variant="primary" size="sm" onClick={save} disabled={!draft.trim()}>
          Save note
        </Button>
      </div>

      {notes.length > 0 && (
        <div className="mt-5 space-y-2">
          <SectionTitle right={<span className="text-2xs text-gray-400">{notes.length}</span>}>
            Notes
          </SectionTitle>
          {notes.map((n) => (
            <div key={n.id} className="group rounded-md border border-hairline p-3">
              <p className="whitespace-pre-line text-sm text-gray-700">{n.body}</p>
              <div className="mt-1.5 flex items-center justify-between">
                <span className="text-2xs text-gray-400" title={dateTime(n.created_at)}>
                  {relTime(n.created_at)}
                </span>
                <button
                  onClick={() => setNotes(deleteNote(personId, n.id))}
                  aria-label="Delete note"
                  className="text-gray-300 opacity-0 transition-opacity hover:text-danger-text group-hover:opacity-100"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
