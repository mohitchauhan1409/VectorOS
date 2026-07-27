import {
  Mail,
  MailOpen,
  Reply,
  Linkedin,
  UserPlus,
  CalendarCheck,
  Radar,
  CircleCheck,
  Send,
  StickyNote,
  Handshake,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { TimelineEvent } from '@/lib/types'
import { relTime, dateTime } from '@/lib/format'

const ICON: Record<string, { icon: LucideIcon; color: string; bg: string }> = {
  signal_detected: { icon: Radar, color: '#1E4A8F', bg: '#E9F0FB' },
  lead_qualified: { icon: CircleCheck, color: '#116335', bg: '#E7F6EE' },
  decision_maker_found: { icon: UserPlus, color: '#5B3F9E', bg: '#F3EDFB' },
  email_sent: { icon: Send, color: '#4B5563', bg: '#F1F5F9' },
  email_opened: { icon: MailOpen, color: '#1E4A8F', bg: '#E9F0FB' },
  email_replied: { icon: Reply, color: '#2A3580', bg: '#EEF1FB' },
  linkedin_invite_sent: { icon: Linkedin, color: '#4B5563', bg: '#F1F5F9' },
  linkedin_accepted: { icon: UserPlus, color: '#116335', bg: '#E7F6EE' },
  linkedin_replied: { icon: Reply, color: '#2A3580', bg: '#EEF1FB' },
  meeting_booked: { icon: CalendarCheck, color: '#0B5128', bg: '#DDF0E4' },
  deal_opened: { icon: Handshake, color: '#5B3F9E', bg: '#F3EDFB' },
  status_change: { icon: CircleCheck, color: '#4B5563', bg: '#F1F5F9' },
  note: { icon: StickyNote, color: '#8A5A0B', bg: '#FBF3E2' },
}

export function Timeline({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) {
    return <p className="py-4 text-sm text-gray-400">No activity yet.</p>
  }
  return (
    <ol className="relative">
      {events.map((e, i) => {
        const cfg = ICON[e.type] ?? ICON.note
        const Icon = cfg.icon
        const last = i === events.length - 1
        return (
          <li key={e.id} className="relative flex gap-3 pb-4 last:pb-0">
            {!last && (
              <span className="absolute left-3 top-6 h-[calc(100%-12px)] w-px bg-hairline" />
            )}
            <span
              className="z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full"
              style={{ background: cfg.bg }}
            >
              <Icon size={13} strokeWidth={1.75} style={{ color: cfg.color }} />
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm font-medium text-gray-800">{e.title}</span>
                <span
                  className="shrink-0 text-2xs text-gray-400"
                  title={dateTime(e.created_at)}
                >
                  {relTime(e.created_at)}
                </span>
              </div>
              {e.detail && (
                <p className="mt-0.5 line-clamp-2 text-sm text-gray-500">{e.detail}</p>
              )}
              {e.meta && <p className="mt-0.5 text-2xs text-gray-400">{e.meta}</p>}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
