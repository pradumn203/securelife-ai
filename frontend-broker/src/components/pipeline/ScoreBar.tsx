import { cn } from '@/lib/utils'

export interface ScoreBarProps {
  /** 0–100 qualification score. Clamped. */
  value: number
  className?: string
  showLabel?: boolean
}

/**
 * Compact 0–100 progress bar for the lead qualification score. Colour shifts
 * from red (<40) → amber (<70) → emerald (>=70) so the broker can scan a grid
 * at a glance.
 */
export function ScoreBar({ value, className, showLabel = true }: ScoreBarProps) {
  const safe = Math.max(0, Math.min(100, Math.round(value)))
  const colour =
    safe >= 70 ? 'bg-emerald-500' : safe >= 40 ? 'bg-amber-500' : 'bg-rose-500'

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={safe}
          className={cn('h-full rounded-full transition-all', colour)}
          style={{ width: `${safe}%` }}
        />
      </div>
      {showLabel && (
        <span className="w-8 text-right text-xs font-semibold tabular-nums text-slate-700">
          {safe}
        </span>
      )}
    </div>
  )
}
