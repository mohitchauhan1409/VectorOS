import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Bell, LogOut, Building2, Users, GitBranch, BarChart3 } from 'lucide-react'
import { CommandPalette } from './CommandPalette'
import { RunPipelineButton } from '@/components/RunPipelineButton'
import { Menu, MenuItem, MenuLabel, MenuSeparator } from '@/components/ui/Menu'
import { Spinner } from '@/components/ui/Misc'
import * as api from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useAsync } from '@/lib/useAsync'
import { usePipeline } from '@/lib/pipeline'
import { initials, relTime, dateTime } from '@/lib/format'

const SEEN_KEY = 'vector_activity_seen_at'

export function TopBar() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const { dataVersion } = usePipeline()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [seenAt, setSeenAt] = useState<string>(() => localStorage.getItem(SEEN_KEY) ?? '')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // The activity feed doubles as the notification source.
  const { data, loading } = useAsync(() => api.getDashboard(), [dataVersion])
  const activity = data?.recent_activity ?? []
  const unread = activity.filter((e) => !seenAt || e.created_at > seenAt).length

  const markSeen = () => {
    const now = new Date().toISOString()
    localStorage.setItem(SEEN_KEY, now)
    setSeenAt(now)
  }

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-4 border-b border-hairline bg-white px-6">
      <button
        onClick={() => setPaletteOpen(true)}
        className="flex h-9 w-[380px] max-w-[38vw] items-center gap-2.5 rounded-sm border border-hairline-strong bg-white px-3 text-sm text-gray-400 transition-colors hover:border-gray-400"
      >
        <Search size={15} />
        <span className="flex-1 text-left">Search people, companies, campaigns…</span>
        <kbd className="rounded-xs bg-gray-100 px-1.5 py-0.5 text-2xs font-medium text-gray-500">
          ⌘K
        </kbd>
      </button>

      <div className="flex-1" />

      <RunPipelineButton />

      <Menu
        width={340}
        trigger={(open) => (
          <button
            onClick={() => !open && markSeen()}
            aria-label={unread ? `${unread} new activity items` : 'Activity'}
            className="relative flex h-8 w-8 items-center justify-center rounded-sm text-gray-500 hover:bg-gray-100 hover:text-gray-900"
          >
            <Bell size={17} strokeWidth={1.75} />
            {unread > 0 && (
              <span className="absolute right-1 top-1 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-danger px-1 text-[9px] font-semibold leading-none text-white tnum">
                {unread > 9 ? '9+' : unread}
              </span>
            )}
          </button>
        )}
      >
        {(close) => (
          <>
            <MenuLabel>Recent activity</MenuLabel>
            {loading && activity.length === 0 ? (
              <div className="flex justify-center py-6">
                <Spinner size={16} className="text-gray-400" />
              </div>
            ) : activity.length === 0 ? (
              <div className="px-2.5 py-6 text-center text-xs text-gray-400">
                Nothing has happened yet.
              </div>
            ) : (
              <div className="max-h-80 overflow-y-auto">
                {activity.map((e) => (
                  <button
                    key={e.id}
                    onClick={() => {
                      close()
                      if (e.person_id) nav(`/people?id=${e.person_id}`)
                    }}
                    className="flex w-full flex-col items-start gap-0.5 rounded-sm px-2.5 py-2 text-left hover:bg-gray-100"
                  >
                    <span className="text-sm font-medium leading-snug text-gray-800">{e.title}</span>
                    {e.detail && (
                      <span className="line-clamp-2 text-xs leading-snug text-gray-500">
                        {e.detail}
                      </span>
                    )}
                    <span className="text-2xs text-gray-400" title={dateTime(e.created_at)}>
                      {relTime(e.created_at)}
                    </span>
                  </button>
                ))}
              </div>
            )}
            <MenuSeparator />
            <MenuItem
              icon={<BarChart3 size={14} />}
              onClick={() => {
                close()
                nav('/analytics')
              }}
            >
              Open analytics
            </MenuItem>
          </>
        )}
      </Menu>

      <Menu
        width={220}
        trigger={() => (
          <button
            aria-label="Account menu"
            className="flex h-8 w-8 items-center justify-center rounded-full bg-[#EEF1FB] text-2xs font-medium text-[#2A3580] hover:bg-[#E2E7F8]"
          >
            {initials(user?.name ?? 'You')}
          </button>
        )}
      >
        {(close) => (
          <>
            <div className="px-2.5 py-2">
              <div className="truncate text-sm font-semibold text-gray-900">{user?.name}</div>
              <div className="truncate text-xs text-gray-500">{user?.email}</div>
              <div className="mt-1 text-2xs text-gray-400">
                {user?.role}
                {user?.is_demo && ' · demo workspace'}
              </div>
            </div>
            <MenuSeparator />
            <MenuItem
              icon={<Users size={14} />}
              onClick={() => {
                close()
                nav('/people')
              }}
            >
              People
            </MenuItem>
            <MenuItem
              icon={<Building2 size={14} />}
              onClick={() => {
                close()
                nav('/companies')
              }}
            >
              Companies
            </MenuItem>
            <MenuItem
              icon={<GitBranch size={14} />}
              onClick={() => {
                close()
                nav('/campaigns')
              }}
            >
              Campaigns
            </MenuItem>
            <MenuSeparator />
            <MenuItem icon={<LogOut size={14} />} onClick={logout} danger>
              Sign out
            </MenuItem>
          </>
        )}
      </Menu>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </header>
  )
}
