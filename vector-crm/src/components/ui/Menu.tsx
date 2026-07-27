import { useEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import type { ReactNode } from 'react'

/** Closes the popover on outside click or Escape. */
export function useDismiss<T extends HTMLElement>(open: boolean, onClose: () => void) {
  const ref = useRef<T>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])
  return ref
}

/**
 * A dropdown anchored to `trigger`. `trigger` gets the current open state so it
 * can render an active style.
 */
export function Menu({
  trigger,
  children,
  align = 'right',
  width = 208,
  className,
}: {
  trigger: (open: boolean) => ReactNode
  children: (close: () => void) => ReactNode
  align?: 'left' | 'right'
  width?: number
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const ref = useDismiss<HTMLDivElement>(open, () => setOpen(false))

  return (
    <div ref={ref} className={clsx('relative', className)}>
      <span onClick={() => setOpen((o) => !o)}>{trigger(open)}</span>
      {open && (
        <div
          style={{ width }}
          className={clsx(
            'absolute top-full z-40 mt-1 rounded-md border border-hairline bg-white p-1 shadow-md animate-fade-in',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  )
}

export function MenuItem({
  icon,
  children,
  onClick,
  disabled,
  danger,
  hint,
}: {
  icon?: ReactNode
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  danger?: boolean
  hint?: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'flex h-8 w-full items-center gap-2.5 rounded-sm px-2.5 text-left text-sm transition-colors',
        disabled
          ? 'cursor-not-allowed text-gray-300'
          : danger
            ? 'text-danger-text hover:bg-danger-bg'
            : 'text-gray-700 hover:bg-gray-100',
      )}
    >
      {icon && <span className="flex shrink-0 text-gray-400">{icon}</span>}
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {hint && <span className="shrink-0 text-2xs text-gray-400">{hint}</span>}
    </button>
  )
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return (
    <div className="px-2.5 pb-1 pt-2 text-2xs font-semibold uppercase tracking-[0.04em] text-gray-400">
      {children}
    </div>
  )
}

export function MenuSeparator() {
  return <div className="my-1 h-px bg-hairline" />
}
