import clsx from 'clsx'
import { initials } from '@/lib/format'

// Deterministic 8-swatch muted palette (DESIGN_SPEC §6.8).
const SWATCHES: Array<{ bg: string; fg: string }> = [
  { bg: '#E9F0FB', fg: '#1E4A8F' },
  { bg: '#E7F6EE', fg: '#116335' },
  { bg: '#FBF3E2', fg: '#8A5A0B' },
  { bg: '#F3EDFB', fg: '#5B3F9E' },
  { bg: '#EEF1FB', fg: '#2A3580' },
  { bg: '#FBEAEA', fg: '#8E2727' },
  { bg: '#F1F5F9', fg: '#374151' },
  { bg: '#E3F1F1', fg: '#0E5C5C' },
]

function hash(str: string): number {
  let h = 0
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0
  return h
}

const SIZES: Record<string, { box: number; text: number }> = {
  xs: { box: 20, text: 9 },
  sm: { box: 24, text: 10 },
  md: { box: 32, text: 12 },
  lg: { box: 40, text: 15 },
  xl: { box: 56, text: 20 },
}

export function Avatar({
  name,
  size = 'md',
  square = false,
  className,
}: {
  name: string
  size?: keyof typeof SIZES
  square?: boolean
  className?: string
}) {
  const s = SIZES[size]
  const sw = SWATCHES[hash(name) % SWATCHES.length]
  return (
    <span
      className={clsx(
        'inline-flex shrink-0 items-center justify-center font-medium select-none',
        square ? 'rounded-sm' : 'rounded-full',
        className,
      )}
      style={{
        width: s.box,
        height: s.box,
        fontSize: s.text,
        background: sw.bg,
        color: sw.fg,
      }}
      aria-hidden
    >
      {initials(name)}
    </span>
  )
}

export function AvatarGroup({
  names,
  max = 3,
  size = 'sm',
}: {
  names: string[]
  max?: number
  size?: keyof typeof SIZES
}) {
  const shown = names.slice(0, max)
  const extra = names.length - shown.length
  return (
    <div className="flex items-center">
      {shown.map((n, i) => (
        <span
          key={i}
          className="ring-2 ring-white rounded-full"
          style={{ marginLeft: i === 0 ? 0 : -8, zIndex: shown.length - i }}
        >
          <Avatar name={n} size={size} />
        </span>
      ))}
      {extra > 0 && (
        <span
          className="ring-2 ring-white rounded-full inline-flex items-center justify-center bg-gray-100 text-gray-600 text-2xs font-medium"
          style={{ marginLeft: -8, width: 24, height: 24 }}
        >
          +{extra}
        </span>
      )}
    </div>
  )
}
