import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { Search, GitBranch, CornerDownLeft } from 'lucide-react'
import * as api from '@/lib/api'
import { useAsync, useDebounced } from '@/lib/useAsync'
import { Avatar } from '@/components/ui/Avatar'
import { Spinner } from '@/components/ui/Misc'
import type { SearchResults } from '@/lib/types'

const EMPTY: SearchResults = { people: [], companies: [], campaigns: [] }

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState('')
  const nav = useNavigate()
  const debounced = useDebounced(q, 250)

  useEffect(() => {
    if (open) setQ('')
  }, [open])

  const { data, loading } = useAsync<SearchResults>(async () => {
    const query = debounced.trim()
    if (!query) return EMPTY
    return api.search(query)
  }, [debounced, open])

  const results = data ?? EMPTY

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (open) window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const go = (path: string) => {
    nav(path)
    onClose()
  }

  const hasQuery = !!debounced.trim()
  const empty =
    !hasQuery ||
    (results.people.length === 0 &&
      results.companies.length === 0 &&
      results.campaigns.length === 0)

  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[12vh]">
      <div className="absolute inset-0" style={{ background: 'rgba(15,20,32,0.20)' }} onClick={onClose} />
      <div className="relative w-[640px] max-w-[92vw] overflow-hidden rounded-md border border-hairline bg-white shadow-lg animate-fade-in">
        <div className="flex items-center gap-3 border-b border-hairline px-4">
          <Search size={17} className="text-gray-400" />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search people, companies, campaigns…"
            className="h-12 flex-1 bg-transparent text-base text-gray-800 placeholder:text-gray-400 focus:outline-none"
          />
          {loading && hasQuery && <Spinner size={15} className="text-gray-400" />}
          <kbd className="rounded-xs bg-gray-100 px-1.5 py-0.5 text-2xs text-gray-500">Esc</kbd>
        </div>
        <div className="max-h-[420px] overflow-y-auto p-2">
          {empty ? (
            <div className="px-3 py-8 text-center text-sm text-gray-400">
              {hasQuery && !loading ? 'No matches found.' : 'Type to search across your workspace.'}
            </div>
          ) : (
            <>
              {results.people.length > 0 && (
                <Group label="People">
                  {results.people.map((p) => (
                    <Row key={p.id} onClick={() => go(`/people?id=${p.id}`)}>
                      <Avatar name={p.name} size="sm" />
                      <span className="font-medium text-gray-800">{p.name}</span>
                      <span className="text-gray-500">
                        {p.title} · {p.company_name}
                      </span>
                      <Enter />
                    </Row>
                  ))}
                </Group>
              )}
              {results.companies.length > 0 && (
                <Group label="Companies">
                  {results.companies.map((c) => (
                    <Row key={c.company_slug} onClick={() => go(`/companies?slug=${c.company_slug}`)}>
                      <Avatar name={c.company_name} size="sm" square />
                      <span className="font-medium text-gray-800">{c.company_name}</span>
                      <span className="text-gray-500">Tier {c.icp.tier} · ICP {c.icp.score}</span>
                      <Enter />
                    </Row>
                  ))}
                </Group>
              )}
              {results.campaigns.length > 0 && (
                <Group label="Campaigns">
                  {results.campaigns.map((c) => (
                    <Row key={c.id} onClick={() => go(`/campaigns?id=${c.id}`)}>
                      <span className="flex h-6 w-6 items-center justify-center rounded-sm bg-gray-100">
                        <GitBranch size={13} className="text-gray-600" />
                      </span>
                      <span className="font-medium text-gray-800">{c.name}</span>
                      <span className="text-gray-500 capitalize">{c.channels.join(' · ')}</span>
                      <Enter />
                    </Row>
                  ))}
                </Group>
              )}
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-1">
      <div className="px-2 py-1 text-2xs font-semibold uppercase tracking-[0.04em] text-gray-400">
        {label}
      </div>
      {children}
    </div>
  )
}

function Row({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="group flex h-10 w-full items-center gap-2.5 rounded-sm px-2 text-sm hover:bg-gray-100"
    >
      {children}
    </button>
  )
}

function Enter() {
  return (
    <span className="ml-auto opacity-0 group-hover:opacity-100">
      <CornerDownLeft size={13} className="text-gray-400" />
    </span>
  )
}
