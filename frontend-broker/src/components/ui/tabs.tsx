import * as React from 'react'
import { cn } from '@/lib/utils'

/**
 * Lightweight controlled Tabs primitive.
 *
 * Headless rather than a full Radix-style context — the dashboard just needs
 * a strip of buttons that reflect the active filter.
 */
export interface TabsProps<T extends string> {
  value: T
  onValueChange: (value: T) => void
  options: Array<{ value: T; label: React.ReactNode; count?: number }>
  className?: string
}

export function Tabs<T extends string>({ value, onValueChange, options, className }: TabsProps<T>) {
  return (
    <div
      role="tablist"
      aria-orientation="horizontal"
      className={cn(
        'inline-flex items-center gap-1 rounded-full bg-mist p-1',
        className
      )}
    >
      {options.map((opt) => {
        const active = opt.value === value
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onValueChange(opt.value)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-semibold transition-colors',
              active
                ? 'bg-ink text-white'
                : 'text-muted hover:text-ink'
            )}
          >
            <span>{opt.label}</span>
            {opt.count !== undefined && (
              <span
                className={cn(
                  'rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none',
                  active ? 'bg-lime text-ink' : 'bg-white text-muted'
                )}
              >
                {opt.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
