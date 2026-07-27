import {
  Banknote,
  Users,
  TrendingUp,
  Rocket,
  UserPlus,
  Handshake,
  Award,
  Newspaper,
  BadgeCheck,
  HelpCircle,
  CircleDashed,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export const SIGNAL_ICON: Record<string, LucideIcon> = {
  funding: Banknote,
  hiring: Users,
  expansion: TrendingUp,
  product_launch: Rocket,
  leadership_hire: UserPlus,
  merger_acquisition: Handshake,
  partnership: Handshake,
  award_recognition: Award,
  other: Newspaper,
}

export function SignalIcon({ signal, size = 12 }: { signal: string; size?: number }) {
  const Icon = SIGNAL_ICON[signal] ?? Newspaper
  return <Icon size={size} strokeWidth={1.75} />
}

export const EMAIL_STATUS_ICON: Record<string, LucideIcon> = {
  verified: BadgeCheck,
  guessed: HelpCircle,
  unverified: CircleDashed,
}
