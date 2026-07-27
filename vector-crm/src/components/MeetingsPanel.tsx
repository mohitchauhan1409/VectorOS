import { useEffect, useState } from 'react'
import {
  CalendarPlus,
  CalendarCheck,
  CalendarClock,
  CircleAlert,
  CircleCheck,
  ExternalLink,
  FileText,
  Handshake,
  HelpCircle,
  Sparkles,
  Trash2,
  Users,
  Video,
  X,
  Check,
} from 'lucide-react'
import clsx from 'clsx'
import type { LucideIcon } from 'lucide-react'
import { Badge, SentimentBadge } from '@/components/ui/Badge'
import { Button, IconButton } from '@/components/ui/Button'
import { SectionTitle, Spinner } from '@/components/ui/Misc'
import * as api from '@/lib/api'
import { dateTime } from '@/lib/format'
import { MEETING_KINDS, type Meeting } from '@/lib/types'

/**
 * Every meeting with a contact — upcoming and held. Always available, whether
 * or not a deal exists.
 *
 * All mutations are optimistic: the UI updates immediately and rolls back if
 * the request fails, so logging a meeting never feels like waiting on a server.
 */
export function MeetingsPanel({
  personId,
  personName,
  initial,
  onCountChange,
}: {
  personId: string
  personName: string
  initial: Meeting[]
  onCountChange?: (meetings: Meeting[]) => void
}) {
  const [meetings, setMeetings] = useState<Meeting[]>(initial)
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<Set<string>>(new Set())

  useEffect(() => {
    setMeetings(initial)
    setAdding(false)
    setError(null)
  }, [initial, personId])

  const apply = (next: Meeting[]) => {
    setMeetings(next)
    onCountChange?.(next)
  }

  const markBusy = (id: string, on: boolean) =>
    setBusy((prev) => {
      const next = new Set(prev)
      if (on) next.add(id)
      else next.delete(id)
      return next
    })

  // ---- optimistic mutations ----

  const create = async (input: api.MeetingInput) => {
    const tempId = `temp-${Date.now()}`
    const optimistic: Meeting = {
      id: tempId,
      person_id: personId,
      deal_id: null,
      title: input.title,
      kind: input.kind,
      status: input.status ?? (new Date(input.occurred_at) <= new Date() ? 'completed' : 'scheduled'),
      occurred_at: input.occurred_at,
      duration_min: input.duration_min,
      attendees: (input.attendees ?? '').split(',').map((a) => a.trim()).filter(Boolean),
      location: input.location ?? '',
      sentiment: 'neutral',
      notes: input.notes ?? '',
      summary: '',
      source: 'manual',
      recording_url: null,
      has_summary: false,
      takeaways: [],
      objections: [],
      questions: [],
      commitments: [],
    }
    const before = meetings
    apply(sortMeetings([optimistic, ...before]))
    setAdding(false)
    setError(null)
    try {
      const saved = await api.createMeeting(personId, input)
      apply(sortMeetings([saved, ...before]))
    } catch (err) {
      apply(before)
      setError(err instanceof Error ? err.message : 'Could not save the meeting.')
      setAdding(true)
    }
  }

  const patch = async (id: string, body: Parameters<typeof api.updateMeeting>[1]) => {
    const before = meetings
    apply(
      sortMeetings(
        meetings.map((m) =>
          m.id === id
            ? { ...m, ...body, has_summary: body.summary !== undefined ? !!body.summary : m.has_summary }
            : m,
        ) as Meeting[],
      ),
    )
    markBusy(id, true)
    setError(null)
    try {
      const saved = await api.updateMeeting(id, body)
      apply(sortMeetings(before.map((m) => (m.id === id ? saved : m))))
    } catch (err) {
      apply(before)
      setError(err instanceof Error ? err.message : 'Could not update the meeting.')
    } finally {
      markBusy(id, false)
    }
  }

  const remove = async (id: string) => {
    const before = meetings
    apply(meetings.filter((m) => m.id !== id))
    setError(null)
    try {
      await api.deleteMeeting(id)
    } catch (err) {
      apply(before)
      setError(err instanceof Error ? err.message : 'Could not delete the meeting.')
    }
  }

  const upcoming = meetings.filter((m) => m.status === 'scheduled')
  const held = meetings.filter((m) => m.status === 'completed')
  const cancelled = meetings.filter((m) => m.status === 'cancelled')

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-600">
          {meetings.length === 0
            ? 'No meetings yet.'
            : `${held.length} held · ${upcoming.length} upcoming`}
        </div>
        <Button
          variant={adding ? 'secondary' : 'primary'}
          size="sm"
          icon={adding ? <X size={14} /> : <CalendarPlus size={14} />}
          onClick={() => setAdding((a) => !a)}
        >
          {adding ? 'Cancel' : 'Log meeting'}
        </Button>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-md border border-[#E7B4B4] bg-danger-bg px-3 py-2 text-sm text-danger-text">
          <CircleAlert size={15} className="mt-0.5 shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)} aria-label="Dismiss">
            <X size={14} />
          </button>
        </div>
      )}

      {adding && <MeetingForm personName={personName} onSubmit={create} onCancel={() => setAdding(false)} />}

      {meetings.length === 0 && !adding && (
        <div className="rounded-md border border-dashed border-hairline-strong px-4 py-10 text-center">
          <CalendarClock size={26} strokeWidth={1.5} className="mx-auto text-gray-300" />
          <p className="mt-3 text-sm font-medium text-gray-700">No meetings with {personName} yet</p>
          <p className="mx-auto mt-1 max-w-xs text-sm text-gray-500">
            Log one manually, or it appears here automatically once Pulse books a call.
          </p>
        </div>
      )}

      {upcoming.length > 0 && (
        <section>
          <SectionTitle right={<span className="text-2xs text-gray-400">{upcoming.length}</span>}>
            Upcoming
          </SectionTitle>
          <div className="space-y-2">
            {upcoming.map((m) => (
              <MeetingCard
                key={m.id}
                meeting={m}
                busy={busy.has(m.id)}
                onPatch={patch}
                onDelete={remove}
              />
            ))}
          </div>
        </section>
      )}

      {held.length > 0 && (
        <section>
          <SectionTitle right={<span className="text-2xs text-gray-400">{held.length}</span>}>
            Held
          </SectionTitle>
          <div className="space-y-2">
            {held.map((m) => (
              <MeetingCard
                key={m.id}
                meeting={m}
                busy={busy.has(m.id)}
                onPatch={patch}
                onDelete={remove}
              />
            ))}
          </div>
        </section>
      )}

      {cancelled.length > 0 && (
        <section>
          <SectionTitle>Cancelled</SectionTitle>
          <div className="space-y-2 opacity-60">
            {cancelled.map((m) => (
              <MeetingCard
                key={m.id}
                meeting={m}
                busy={busy.has(m.id)}
                onPatch={patch}
                onDelete={remove}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

/** Upcoming soonest-first at the top, held most-recent-first below. */
function sortMeetings(list: Meeting[]): Meeting[] {
  return [...list].sort((a, b) => {
    if (a.status === 'scheduled' && b.status === 'scheduled') {
      return a.occurred_at.localeCompare(b.occurred_at)
    }
    return b.occurred_at.localeCompare(a.occurred_at)
  })
}

// --------------------------------------------------------------------------- //
// Card
// --------------------------------------------------------------------------- //

const KIND_ICON: Record<string, LucideIcon> = {
  intro: Handshake,
  discovery: HelpCircle,
  demo: Sparkles,
  technical: FileText,
  pricing: CalendarCheck,
  exec: Users,
  other: CalendarClock,
}

function MeetingCard({
  meeting: m,
  busy,
  onPatch,
  onDelete,
}: {
  meeting: Meeting
  busy: boolean
  onPatch: (id: string, body: Parameters<typeof api.updateMeeting>[1]) => void
  onDelete: (id: string) => void
}) {
  const [showSummary, setShowSummary] = useState(false)
  const [editingNotes, setEditingNotes] = useState(false)
  const [draft, setDraft] = useState(m.notes)

  const Icon = KIND_ICON[m.kind] ?? CalendarClock
  const scheduled = m.status === 'scheduled'
  const pointCount =
    m.takeaways.length + m.objections.length + m.questions.length + m.commitments.length
  const pending = m.id.startsWith('temp-')

  return (
    <div className={clsx('rounded-md border', scheduled ? 'border-brand-200 bg-brand-50/40' : 'border-hairline')}>
      <div className="p-3">
        <div className="flex items-start gap-2.5">
          <span
            className={clsx(
              'mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full',
              scheduled ? 'bg-brand-100' : 'bg-gray-100',
            )}
          >
            <Icon size={14} className={scheduled ? 'text-brand-700' : 'text-gray-600'} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <span className="text-sm font-semibold leading-snug text-gray-900">{m.title}</span>
              <div className="flex shrink-0 items-center gap-1.5">
                {pending && <Spinner size={13} className="text-gray-400" />}
                {scheduled ? (
                  <Badge tone="brand" dot>
                    Upcoming
                  </Badge>
                ) : m.status === 'cancelled' ? (
                  <Badge tone="neutral">cancelled</Badge>
                ) : (
                  <SentimentBadge sentiment={m.sentiment} />
                )}
              </div>
            </div>

            <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-2xs text-gray-500">
              <span className="font-medium text-gray-600">{dateTime(m.occurred_at)}</span>
              <span>·</span>
              <span>{m.duration_min} min</span>
              <span>·</span>
              <span className="capitalize">{m.kind}</span>
            </div>

            {m.attendees.length > 0 && (
              <div className="mt-1.5 flex items-start gap-1.5 text-2xs text-gray-500">
                <Users size={11} className="mt-0.5 shrink-0 text-gray-400" />
                <span>{m.attendees.join(', ')}</span>
              </div>
            )}

            {m.location && (
              <a
                href={m.location}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-2xs text-brand-600 hover:underline"
              >
                <Video size={11} /> Join link
              </a>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          {scheduled && (
            <Button
              variant="secondary"
              size="sm"
              icon={busy ? <Spinner size={13} /> : <Check size={13} />}
              disabled={busy || pending}
              onClick={() => onPatch(m.id, { status: 'completed' })}
            >
              Mark as held
            </Button>
          )}

          {m.status === 'completed' && m.has_summary && (
            <Button
              variant="secondary"
              size="sm"
              icon={<FileText size={13} />}
              onClick={() => setShowSummary((s) => !s)}
            >
              {showSummary ? 'Hide summary' : 'View summary'}
            </Button>
          )}

          {m.status === 'completed' && !m.has_summary && !editingNotes && (
            <Button
              variant="secondary"
              size="sm"
              icon={<FileText size={13} />}
              disabled={pending}
              onClick={() => {
                setDraft(m.notes)
                setEditingNotes(true)
              }}
            >
              {m.notes ? 'Edit notes' : 'Add notes'}
            </Button>
          )}

          {m.recording_url && (
            <a
              href={m.recording_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-2xs text-gray-500 hover:text-gray-800"
            >
              Recording <ExternalLink size={10} />
            </a>
          )}

          <div className="flex-1" />
          {scheduled && (
            <button
              onClick={() => onPatch(m.id, { status: 'cancelled' })}
              disabled={busy || pending}
              className="text-2xs text-gray-400 hover:text-gray-700 disabled:opacity-50"
            >
              Cancel meeting
            </button>
          )}
          <IconButton
            size="sm"
            aria-label="Delete meeting"
            title="Delete meeting"
            disabled={pending}
            onClick={() => onDelete(m.id)}
          >
            <Trash2 size={13} />
          </IconButton>
        </div>

        {/* Manual notes editor — what Closer will turn into a summary */}
        {editingNotes && (
          <div className="mt-2.5">
            <textarea
              autoFocus
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="What was said? Paste your notes or the transcript — Closer turns this into a summary."
              className="h-24 w-full resize-none rounded-sm border border-hairline-strong p-2.5 text-sm placeholder:text-gray-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/35"
            />
            <div className="mt-1.5 flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setEditingNotes(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  onPatch(m.id, { notes: draft })
                  setEditingNotes(false)
                }}
              >
                Save notes
              </Button>
            </div>
          </div>
        )}

        {!editingNotes && m.notes && !m.has_summary && (
          <div className="mt-2.5 rounded-sm bg-sunken p-2.5">
            <div className="mb-1 text-2xs font-semibold uppercase tracking-[0.04em] text-gray-500">
              Your notes
            </div>
            <p className="whitespace-pre-line text-sm text-gray-700">{m.notes}</p>
            <p className="mt-2 flex items-center gap-1.5 text-2xs text-gray-400">
              <Sparkles size={11} /> Closer will turn these into a summary and next steps.
            </p>
          </div>
        )}
      </div>

      {/* Summary */}
      {showSummary && m.has_summary && (
        <div className="space-y-3 border-t border-hairline bg-sunken p-3">
          <div>
            <div className="mb-1 flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-[0.04em] text-gray-500">
              <Sparkles size={11} /> Summary
            </div>
            <p className="text-sm leading-relaxed text-gray-700">{m.summary}</p>
          </div>
          {pointCount > 0 && (
            <>
              <PointList label="Takeaways" icon={CircleCheck} items={m.takeaways} color="#116335" />
              <PointList label="Objections" icon={CircleAlert} items={m.objections} color="#8A5A0B" />
              <PointList label="Open questions" icon={HelpCircle} items={m.questions} color="#1E4A8F" />
              <PointList label="Commitments" icon={Handshake} items={m.commitments} color="#5B3F9E" />
            </>
          )}
        </div>
      )}
    </div>
  )
}

function PointList({
  label,
  icon: Icon,
  items,
  color,
}: {
  label: string
  icon: LucideIcon
  items: string[]
  color: string
}) {
  if (items.length === 0) return null
  return (
    <div>
      <div className="mb-1 flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-[0.04em] text-gray-500">
        <Icon size={11} style={{ color }} />
        {label}
      </div>
      <ul className="space-y-1">
        {items.map((t, i) => (
          <li key={i} className="flex gap-2 text-sm leading-snug text-gray-700">
            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full" style={{ background: color }} />
            {t}
          </li>
        ))}
      </ul>
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Add form
// --------------------------------------------------------------------------- //

/** `datetime-local` wants local wall-clock with no zone suffix. */
function localInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function MeetingForm({
  personName,
  onSubmit,
  onCancel,
}: {
  personName: string
  onSubmit: (input: api.MeetingInput) => void
  onCancel: () => void
}) {
  const [title, setTitle] = useState('Intro call')
  const [kind, setKind] = useState<string>('intro')
  const [when, setWhen] = useState(() => {
    const d = new Date()
    d.setMinutes(0, 0, 0)
    d.setHours(d.getHours() + 1)
    return localInputValue(d)
  })
  const [duration, setDuration] = useState(30)
  const [attendees, setAttendees] = useState(personName)
  const [location, setLocation] = useState('')
  const [notes, setNotes] = useState('')

  const isPast = new Date(when) <= new Date()

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    onSubmit({
      title: title.trim(),
      kind,
      occurred_at: new Date(when).toISOString(),
      duration_min: duration,
      attendees,
      location,
      notes,
    })
  }

  return (
    <form onSubmit={submit} className="rounded-md border border-hairline bg-white p-3">
      <div className="mb-3 text-2xs font-semibold uppercase tracking-[0.04em] text-gray-500">
        Log a meeting
      </div>

      <div className="space-y-2.5">
        <Field label="Title">
          <input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            className={inputCls}
          />
        </Field>

        <div className="grid grid-cols-2 gap-2.5">
          <Field label="Type">
            <select value={kind} onChange={(e) => setKind(e.target.value)} className={inputCls}>
              {MEETING_KINDS.map((k) => (
                <option key={k} value={k}>
                  {k[0].toUpperCase() + k.slice(1)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Duration (min)">
            <input
              type="number"
              min={5}
              max={600}
              step={5}
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className={inputCls}
            />
          </Field>
        </div>

        <Field label="Date & time" hint={isPast ? 'Logged as held' : 'Logged as upcoming'}>
          <input
            type="datetime-local"
            value={when}
            onChange={(e) => setWhen(e.target.value)}
            required
            className={inputCls}
          />
        </Field>

        <Field label="Attendees">
          <input
            value={attendees}
            onChange={(e) => setAttendees(e.target.value)}
            placeholder="Comma separated"
            className={inputCls}
          />
        </Field>

        <Field label="Join link" optional>
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="https://meet.google.com/…"
            className={inputCls}
          />
        </Field>

        {isPast && (
          <Field label="Notes" optional>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="What was said? Closer turns this into a summary."
              className="h-20 w-full resize-none rounded-sm border border-hairline-strong p-2.5 text-sm placeholder:text-gray-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/35"
            />
          </Field>
        )}
      </div>

      <div className="mt-3 flex justify-end gap-2">
        <Button variant="ghost" size="sm" type="button" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" size="sm" type="submit" disabled={!title.trim()}>
          {isPast ? 'Log meeting' : 'Schedule meeting'}
        </Button>
      </div>
    </form>
  )
}

const inputCls =
  'h-8 w-full rounded-sm border border-hairline-strong bg-white px-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/35'

function Field({
  label,
  hint,
  optional,
  children,
}: {
  label: string
  hint?: string
  optional?: boolean
  children: React.ReactNode
}) {
  return (
    <label className="block">
      <span className="mb-1 flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-[0.04em] text-gray-500">
        {label}
        {optional && <span className="font-normal normal-case tracking-normal text-gray-400">(optional)</span>}
        {hint && <span className="ml-auto font-normal normal-case tracking-normal text-gray-400">{hint}</span>}
      </span>
      {children}
    </label>
  )
}
