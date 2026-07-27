import clsx from 'clsx'
import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-brand-600 text-white hover:bg-brand-700 active:bg-brand-800 disabled:bg-gray-200 disabled:text-gray-400',
  secondary:
    'bg-white text-gray-700 border border-hairline-strong hover:bg-gray-50 hover:border-gray-400 hover:text-gray-900 active:bg-gray-100 disabled:text-gray-400 disabled:border-hairline',
  ghost:
    'bg-transparent text-gray-600 hover:bg-gray-100 hover:text-gray-900 active:bg-gray-200 disabled:text-gray-400',
  danger:
    'bg-white text-danger-text border border-[#E7B4B4] hover:bg-danger-bg disabled:text-gray-400',
}

const SIZES: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-2xs gap-1.5',
  md: 'h-8 px-3 text-sm gap-1.5',
  lg: 'h-10 px-4 text-base gap-2',
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  icon?: ReactNode
  iconRight?: ReactNode
}

export function Button({
  variant = 'secondary',
  size = 'md',
  icon,
  iconRight,
  className,
  children,
  ...rest
}: Props) {
  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center rounded-sm font-medium transition-colors duration-100 focus-ring disabled:cursor-not-allowed whitespace-nowrap',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    >
      {icon}
      {children}
      {iconRight}
    </button>
  )
}

export function IconButton({
  variant = 'ghost',
  size = 'md',
  className,
  children,
  ...rest
}: Omit<Props, 'icon' | 'iconRight'>) {
  const dim = size === 'sm' ? 'h-7 w-7' : size === 'lg' ? 'h-10 w-10' : 'h-8 w-8'
  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center rounded-sm transition-colors duration-100 focus-ring disabled:cursor-not-allowed',
        VARIANTS[variant],
        dim,
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}
