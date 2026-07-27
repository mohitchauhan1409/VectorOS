import { formatDistanceToNow, format, parseISO } from 'date-fns'

export function relTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    const d = parseISO(iso)
    return formatDistanceToNow(d, { addSuffix: true })
  } catch {
    return '—'
  }
}

export function dateTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    return format(parseISO(iso), 'MMM d, yyyy · h:mm a')
  } catch {
    return iso
  }
}

export function dateOnly(iso: string | null): string {
  if (!iso) return '—'
  try {
    return format(parseISO(iso), 'MMM d, yyyy')
  } catch {
    return iso
  }
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export function pct(n: number, digits = 1): string {
  return `${(n * 100).toFixed(digits)}%`
}

export function titleCase(s: string): string {
  return s
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function compactNumber(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

/** Deal values are whole dollars — show them compactly ($48k, $1.2M). */
export function money(n: number): string {
  if (!n) return '$0'
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(n % 1_000_000 === 0 ? 0 : 1)}M`
  if (n >= 1000) return `$${(n / 1000).toFixed(n % 1000 === 0 ? 0 : 1)}k`
  return `$${n.toLocaleString()}`
}

/** Days from now to an ISO date — negative when overdue. */
export function daysUntil(iso: string | null): number | null {
  if (!iso) return null
  try {
    const target = parseISO(iso).getTime()
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    return Math.round((target - today.getTime()) / 86_400_000)
  } catch {
    return null
  }
}

/** "in 3 days" / "today" / "4 days overdue" — for deal due dates. */
export function dueLabel(iso: string | null): string {
  const d = daysUntil(iso)
  if (d === null) return 'No date'
  if (d === 0) return 'Due today'
  if (d === 1) return 'Due tomorrow'
  if (d > 1) return `Due in ${d} days`
  if (d === -1) return '1 day overdue'
  return `${Math.abs(d)} days overdue`
}

// Muted, evenly-distributed avatar background derived from a hue.
// Keeps a professional, desaturated look (no loud colors, no gradients).
export function avatarColor(hue: number): { bg: string; fg: string } {
  return {
    bg: `hsl(${hue}, 32%, 92%)`,
    fg: `hsl(${hue}, 38%, 32%)`,
  }
}
