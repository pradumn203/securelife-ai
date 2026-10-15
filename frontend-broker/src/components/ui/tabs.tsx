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
        'inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1',
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
              'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              active
                ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200'
                : 'text-slate-600 hover:text-slate-900'
            )}
          >
            <span>{opt.label}</span>
            {opt.count !== undefined && (
              <span
                className={cn(
                  'rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none',
                  active ? 'bg-brand-100 text-brand-700' : 'bg-slate-200 text-slate-600'
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
