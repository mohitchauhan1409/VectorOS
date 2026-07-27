import clsx from 'clsx'
import { Search, X } from 'lucide-react'
import type { InputHTMLAttributes, ReactNode } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  leading?: ReactNode
  trailing?: ReactNode
}

export function Input({ leading, trailing, className, ...rest }: InputProps) {
  return (
    <div className="relative flex items-center">
      {leading && (
        <span className="absolute left-3 text-gray-400 pointer-events-none flex">{leading}</span>
      )}
      <input
        className={clsx(
          'h-8 w-full rounded-sm border border-hairline-strong bg-white text-sm text-gray-800 placeholder:text-gray-400 transition-colors duration-100',
          'hover:border-gray-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/35',
          leading ? 'pl-9' : 'pl-3',
          trailing ? 'pr-9' : 'pr-3',
          className,
        )}
        {...rest}
      />
      {trailing && <span className="absolute right-3 flex">{trailing}</span>}
    </div>
  )
}

export function SearchInput({
  value,
  onChange,
  placeholder = 'Search this list…',
  className,
  onClear,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  className?: string
  onClear?: () => void
}) {
  return (
    <Input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={className}
      leading={<Search size={15} />}
      trailing={
        value ? (
          <button
            onClick={() => (onClear ? onClear() : onChange(''))}
            className="text-gray-400 hover:text-gray-700"
            aria-label="Clear search"
          >
            <X size={15} />
          </button>
        ) : undefined
      }
    />
  )
}
