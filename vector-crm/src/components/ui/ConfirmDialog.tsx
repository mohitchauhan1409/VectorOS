import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { TriangleAlert, X } from 'lucide-react'
import clsx from 'clsx'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Misc'

/**
 * Blocking confirmation for actions that reach the outside world — the kind
 * where "are you sure" is genuinely load-bearing rather than decoration.
 */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  tone = 'danger',
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean
  title: string
  children: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  tone?: 'danger' | 'warning' | 'brand'
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, busy, onCancel])

  if (!open) return null

  const iconCls = {
    danger: 'bg-danger-bg text-danger-text',
    warning: 'bg-warning-bg text-warning-text',
    brand: 'bg-brand-50 text-brand-700',
  }[tone]

  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 animate-fade-in"
        style={{ background: 'rgba(15,20,32,0.28)' }}
        onClick={() => !busy && onCancel()}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative w-full max-w-md overflow-hidden rounded-md border border-hairline bg-white shadow-lg animate-fade-in"
      >
        <div className="flex items-start gap-3 p-5">
          <span className={clsx('flex h-9 w-9 shrink-0 items-center justify-center rounded-full', iconCls)}>
            <TriangleAlert size={18} />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold text-gray-900">{title}</h2>
            <div className="mt-1.5 text-sm leading-relaxed text-gray-600">{children}</div>
          </div>
          <button
            onClick={() => !busy && onCancel()}
            aria-label="Close"
            className="shrink-0 text-gray-400 hover:text-gray-700"
          >
            <X size={16} />
          </button>
        </div>
        <div className="flex justify-end gap-2 border-t border-hairline bg-sunken px-5 py-3">
          <Button variant="secondary" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button
            variant={tone === 'brand' ? 'primary' : 'danger'}
            onClick={onConfirm}
            disabled={busy}
            icon={busy ? <Spinner size={14} /> : undefined}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
