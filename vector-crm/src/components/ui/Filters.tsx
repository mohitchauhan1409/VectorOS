import { useEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import { ListFilter, Plus, X, Check, ChevronDown } from 'lucide-react'

export interface FilterField {
  key: string
  label: string
  options: { value: string; label: string }[]
}

export type FilterState = Record<string, string[]>

function useOutside(cb: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) cb()
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [cb])
  return ref
}

function Menu({
  field,
  selected,
  onToggle,
  onClose,
}: {
  field: FilterField
  selected: string[]
  onToggle: (v: string) => void
  onClose: () => void
}) {
  const [q, setQ] = useState('')
  const ref = useOutside(onClose)
  const opts = field.options.filter((o) => o.label.toLowerCase().includes(q.toLowerCase()))
  return (
    <div
      ref={ref}
      className="absolute left-0 top-9 z-30 w-60 rounded-md border border-hairline bg-white p-1 shadow-sm animate-fade-in"
    >
      <div className="p-1">
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={`Filter ${field.label.toLowerCase()}…`}
          className="h-7 w-full rounded-sm border border-hairline-strong px-2 text-sm placeholder:text-gray-400 focus:border-brand-600 focus:outline-none"
        />
      </div>
      <div className="max-h-64 overflow-auto py-1">
        {opts.map((o) => {
          const on = selected.includes(o.value)
          return (
            <button
              key={o.value}
              onClick={() => onToggle(o.value)}
              className="flex h-8 w-full items-center justify-between rounded-sm px-2 text-sm text-gray-700 hover:bg-gray-100"
            >
              <span className="flex items-center gap-2">
                <span
                  className={clsx(
                    'flex h-4 w-4 items-center justify-center rounded-[4px] border',
                    on ? 'border-brand-600 bg-brand-600 text-white' : 'border-hairline-strong',
                  )}
                >
                  {on && <Check size={11} strokeWidth={3} />}
                </span>
                {o.label}
              </span>
            </button>
          )
        })}
        {opts.length === 0 && (
          <div className="px-2 py-3 text-center text-xs text-gray-400">No options</div>
        )}
      </div>
    </div>
  )
}

export function FilterBar({
  fields,
  state,
  onChange,
}: {
  fields: FilterField[]
  state: FilterState
  onChange: (s: FilterState) => void
}) {
  const [openKey, setOpenKey] = useState<string | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const addRef = useOutside(() => setAddOpen(false))

  const toggle = (fieldKey: string, v: string) => {
    const cur = state[fieldKey] ?? []
    const next = cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v]
    const s = { ...state, [fieldKey]: next }
    if (next.length === 0) delete s[fieldKey]
    onChange(s)
  }

  const activeFields = fields.filter((f) => (state[f.key]?.length ?? 0) > 0)
  const inactiveFields = fields.filter((f) => !(state[f.key]?.length ?? 0))
  const anyActive = activeFields.length > 0

  return (
    <div className="flex flex-wrap items-center gap-2">
      {activeFields.map((f) => {
        const vals = state[f.key] ?? []
        const label =
          vals.length === 1
            ? f.options.find((o) => o.value === vals[0])?.label ?? vals[0]
            : `${vals.length} selected`
        return (
          <div key={f.key} className="relative">
            <button
              onClick={() => setOpenKey(openKey === f.key ? null : f.key)}
              className="flex h-7 items-center gap-1.5 rounded-sm border border-brand-200 bg-brand-50 pl-2.5 pr-1.5 text-xs"
            >
              <span className="text-gray-500">{f.label}:</span>
              <span className="font-medium text-gray-800">{label}</span>
              <span
                role="button"
                onClick={(e) => {
                  e.stopPropagation()
                  const s = { ...state }
                  delete s[f.key]
                  onChange(s)
                }}
                className="ml-0.5 flex text-gray-400 hover:text-gray-700"
              >
                <X size={13} />
              </span>
            </button>
            {openKey === f.key && (
              <Menu
                field={f}
                selected={vals}
                onToggle={(v) => toggle(f.key, v)}
                onClose={() => setOpenKey(null)}
              />
            )}
          </div>
        )
      })}

      <div className="relative" ref={addRef}>
        <button
          onClick={() => setAddOpen((o) => !o)}
          className="flex h-7 items-center gap-1.5 rounded-sm border border-dashed border-hairline-strong px-2.5 text-xs text-gray-600 hover:border-gray-400 hover:text-gray-900"
        >
          {anyActive ? <Plus size={13} /> : <ListFilter size={13} />}
          {anyActive ? 'Add filter' : 'Filter'}
          <ChevronDown size={12} className="text-gray-400" />
        </button>
        {addOpen && (
          <div className="absolute left-0 top-9 z-30 w-52 rounded-md border border-hairline bg-white p-1 shadow-sm animate-fade-in">
            {inactiveFields.map((f) => (
              <button
                key={f.key}
                onClick={() => {
                  setAddOpen(false)
                  setOpenKey(f.key)
                }}
                className="flex h-8 w-full items-center rounded-sm px-2 text-sm text-gray-700 hover:bg-gray-100"
              >
                {f.label}
              </button>
            ))}
            {inactiveFields.length === 0 && (
              <div className="px-2 py-3 text-center text-xs text-gray-400">All filters applied</div>
            )}
          </div>
        )}
        {/* hidden menu anchor for opening a filter chosen from add-menu */}
        {openKey && inactiveFields.some((f) => f.key === openKey) && (
          <Menu
            field={fields.find((f) => f.key === openKey)!}
            selected={state[openKey] ?? []}
            onToggle={(v) => toggle(openKey, v)}
            onClose={() => setOpenKey(null)}
          />
        )}
      </div>

      {anyActive && (
        <button
          onClick={() => onChange({})}
          className="text-xs text-gray-500 hover:text-gray-800"
        >
          Clear all
        </button>
      )}
    </div>
  )
}
