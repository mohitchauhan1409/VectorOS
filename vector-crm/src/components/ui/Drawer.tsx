import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import clsx from 'clsx'
import type { ReactNode } from 'react'

export function Drawer({
  open,
  onClose,
  width = 480,
  children,
}: {
  open: boolean
  onClose: () => void
  width?: number
  children: ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-50">
      <div
        className="absolute inset-0 animate-fade-in"
        style={{ background: 'rgba(15,20,32,0.20)' }}
        onClick={onClose}
      />
      <div
        className={clsx(
          'absolute right-0 top-0 h-full bg-white border-l border-hairline shadow-md animate-slide-in flex flex-col',
          'transition-[width] duration-200 ease-out motion-reduce:transition-none',
        )}
        style={{ width: `min(${width}px, 100vw)` }}
      >
        {children}
      </div>
    </div>,
    document.body,
  )
}
