import * as React from 'react'
import { cn } from '@/lib/utils'

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  /** 0–100 inclusive. Values outside this range are clamped. */
  value: number
  /** Optional CSS class for the inner (filled) bar. */
  barClassName?: string
}

/**
 * Minimal determinate progress bar used while an upload is in flight.
 */
export const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ value, className, barClassName, ...props }, ref) => {
    const pct = Math.max(0, Math.min(100, value))
    return (
      <div
        ref={ref}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className={cn(
          'h-1.5 w-full overflow-hidden rounded-full bg-slate-200',
          className
        )}
        {...props}
      >
        <div
          className={cn(
            'h-full rounded-full bg-brand-600 transition-[width] duration-200 ease-out',
            barClassName
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    )
  }
)
Progress.displayName = 'Progress'
