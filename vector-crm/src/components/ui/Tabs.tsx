import clsx from 'clsx'

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string; count?: number }[]
  active: string
  onChange: (key: string) => void
}) {
  return (
    // Scrollable + no-shrink so a tab can never be clipped out of reach when
    // the set grows (Overview · Activity · Emails · Deal · Meetings · Notes).
    <div className="flex items-center gap-5 overflow-x-auto border-b border-hairline scrollbar-none">
      {tabs.map((t) => {
        const isActive = t.key === active
        return (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={clsx(
              'relative flex h-9 shrink-0 items-center gap-2 whitespace-nowrap text-sm font-medium transition-colors -mb-px focus-ring rounded-sm px-0.5',
              isActive ? 'text-gray-900' : 'text-gray-500 hover:text-gray-800',
            )}
          >
            {t.label}
            {t.count !== undefined && (
              <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-gray-100 px-1 text-2xs font-medium text-gray-600 tnum">
                {t.count}
              </span>
            )}
            {isActive && (
              <span className="absolute -bottom-px left-0 right-0 h-0.5 rounded-full bg-brand-600" />
            )}
          </button>
        )
      })}
    </div>
  )
}

export function Segmented({
  options,
  value,
  onChange,
}: {
  options: { key: string; label: string }[]
  value: string
  onChange: (k: string) => void
}) {
  return (
    <div className="inline-flex h-7 items-center rounded-sm bg-gray-100 p-0.5">
      {options.map((o) => {
        const active = o.key === value
        return (
          <button
            key={o.key}
            onClick={() => onChange(o.key)}
            className={clsx(
              'h-6 rounded-[4px] px-2.5 text-2xs font-medium transition-colors',
              active ? 'bg-white text-gray-900 shadow-xs' : 'text-gray-500 hover:text-gray-800',
            )}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
