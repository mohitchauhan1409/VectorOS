import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import clsx from 'clsx'
import {
  LayoutDashboard,
  BarChart3,
  Users,
  Building2,
  Bookmark,
  GitBranch,
  Inbox,
  Radar,
  Settings,
  LifeBuoy,
  LogOut,
  ChevronDown,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import * as api from '@/lib/api'
import { useAsync } from '@/lib/useAsync'
import { useAuth } from '@/lib/auth'
import { usePipeline } from '@/lib/pipeline'
import { initials } from '@/lib/format'

interface Item {
  to: string
  label: string
  icon: LucideIcon
  count?: number
  dot?: boolean
}

function NavItem({ item }: { item: Item }) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) =>
        clsx(
          'group relative mx-2 flex h-9 items-center gap-2.5 rounded-sm px-3 text-sm transition-colors',
          isActive
            ? 'bg-brand-50 font-semibold text-brand-700'
            : 'font-medium text-gray-700 hover:bg-gray-100 hover:text-gray-900',
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-brand-600" />
          )}
          <Icon
            size={16}
            strokeWidth={1.75}
            className={isActive ? 'text-brand-600' : 'text-gray-500 group-hover:text-gray-700'}
          />
          <span className="flex-1">{item.label}</span>
          {item.count !== undefined && (
            <span
              className={clsx(
                'inline-flex h-4 min-w-5 items-center justify-center rounded-full px-1 text-2xs font-medium tnum',
                isActive ? 'bg-brand-100 text-brand-700' : 'bg-gray-100 text-gray-600',
              )}
            >
              {item.count}
            </span>
          )}
          {item.dot && <span className="h-1.5 w-1.5 rounded-full bg-brand-600" />}
        </>
      )}
    </NavLink>
  )
}

export function Sidebar() {
  const { user, logout } = useAuth()
  const { dataVersion } = usePipeline()

  const counts = useAsync(async () => {
    const [people, companies, campaigns] = await Promise.all([
      api.getPeople({ page_size: 1 }),
      api.getCompanies({}),
      api.getCampaigns(),
    ])
    return {
      people: people.total,
      companies: companies.total,
      campaigns: campaigns.total,
    }
  }, [dataVersion])

  const c = counts.data

  const sections: { label?: string; items: Item[] }[] = [
    {
      label: 'Overview',
      items: [
        { to: '/', label: 'Dashboard', icon: LayoutDashboard },
        { to: '/analytics', label: 'Analytics', icon: BarChart3 },
      ],
    },
    {
      label: 'Data',
      items: [
        { to: '/people', label: 'People', icon: Users, count: c?.people },
        { to: '/companies', label: 'Companies', icon: Building2, count: c?.companies },
        { to: '/lists', label: 'Lists', icon: Bookmark },
      ],
    },
    {
      label: 'Outreach · Pulse',
      items: [
        { to: '/campaigns', label: 'Campaigns', icon: GitBranch, count: c?.campaigns },
        { to: '/inbox', label: 'Inbox', icon: Inbox, dot: true },
        { to: '/signals', label: 'Signals', icon: Radar },
      ],
    },
  ]

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-hairline bg-white">
      {/* Workspace switcher */}
      <div className="flex h-14 items-center gap-2.5 px-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-600">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 3.5L8 12.5L14 3.5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div className="flex-1">
          <div className="text-sm font-bold leading-tight text-gray-900">Vector</div>
          <div className="text-2xs text-gray-500">Konfyd</div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto pb-4">
        {sections.map((section, i) => (
          <div key={i} className="mt-4 first:mt-2">
            {section.label && (
              <div className="px-4 pb-1 pt-1 text-2xs font-semibold uppercase tracking-[0.04em] text-gray-500">
                {section.label}
              </div>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <NavItem key={item.to} item={item} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Pinned bottom */}
      <div className="border-t border-hairline p-2">
        <div className="space-y-0.5">
          <NavItem item={{ to: '/settings', label: 'Settings', icon: Settings }} />
          <NavItem item={{ to: '/help', label: 'Help & docs', icon: LifeBuoy }} />
        </div>
        <UserChip name={user?.name ?? 'You'} role={user?.role ?? ''} onLogout={logout} />
      </div>
    </aside>
  )
}

function UserChip({ name, role, onLogout }: { name: string; role: string; onLogout: () => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  return (
    <div ref={ref} className="relative mt-2">
      {open && (
        <div className="absolute bottom-full left-0 right-0 mb-1 rounded-md border border-hairline bg-white p-1 shadow-sm animate-fade-in">
          <button
            onClick={onLogout}
            className="flex h-8 w-full items-center gap-2.5 rounded-sm px-2.5 text-sm text-gray-700 hover:bg-gray-100"
          >
            <LogOut size={15} className="text-gray-500" />
            Sign out
          </button>
        </div>
      )}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2.5 rounded-sm px-3 py-2 text-left hover:bg-gray-100"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#EEF1FB] text-2xs font-medium text-[#2A3580]">
          {initials(name)}
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-gray-800">{name}</div>
          <div className="truncate text-2xs text-gray-500">{role}</div>
        </div>
        <ChevronDown size={14} className="text-gray-400" />
      </button>
    </div>
  )
}
