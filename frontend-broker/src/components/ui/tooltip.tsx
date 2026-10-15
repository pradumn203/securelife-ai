import * as React from 'react'
import { cn } from '@/lib/utils'

export interface TooltipProps {
  /** The content rendered inside the floating panel. */
  content: React.ReactNode
  /** The hover/focus trigger. Should be a single element. */
  children: React.ReactNode
  /** Preferred side; the panel will clamp to the viewport anyway. */
  side?: 'top' | 'bottom' | 'left' | 'right'
  /** Max width of the floating panel. */
  className?: string
  /** When true, the trigger gets no tooltip at all (disabled state). */
  disabled?: boolean
}

/**
 * Lightweight hover tooltip. We deliberately avoid pulling in Radix for a
 * single primitive — this is enough for evidence pills + disabled-button
 * explanations. Keyboard focus triggers it too.
 */
export function Tooltip({
  content,
  children,
  side = 'top',
  className,
  disabled,
}: TooltipProps) {
  const [open, setOpen] = React.useState(false)
  if (disabled) return <>{children}</>
  const sideClass =
    side === 'top'
      ? 'bottom-full left-1/2 mb-2 -translate-x-1/2'
      : side === 'bottom'
        ? 'top-full left-1/2 mt-2 -translate-x-1/2'
        : side === 'left'
          ? 'right-full top-1/2 mr-2 -translate-y-1/2'
          : 'left-full top-1/2 ml-2 -translate-y-1/2'
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open ? (
        <span
          role="tooltip"
          className={cn(
            'pointer-events-none absolute z-50 w-max max-w-xs rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-xs text-slate-700 shadow-lg',
            sideClass,
            className
          )}
        >
          {content}
        </span>
      ) : null}
    </span>
  )
}
