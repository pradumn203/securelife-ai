import type { components } from '@/api/types'
import { cn } from '@/lib/utils'

type CoverageGap = components['schemas']['CoverageGap']
type Severity = CoverageGap['severity']

export interface GapListProps {
  gaps: CoverageGap[]
}

const SEVERITY_DOT: Record<Severity, string> = {
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-slate-400',
}

const SEVERITY_LABEL_CLASS: Record<Severity, string> = {
  high: 'text-red-700 bg-red-50 border-red-200',
  medium: 'text-amber-800 bg-amber-50 border-amber-200',
  low: 'text-slate-600 bg-slate-50 border-slate-200',
}

export function GapList({ gaps }: GapListProps) {
  if (gaps.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No coverage gaps detected.
      </p>
    )
  }
  return (
    <ul className="space-y-2">
      {gaps.map((gap, i) => (
        <li
          key={`${gap.area}-${i}`}
          className="flex items-start gap-3 rounded-lg border border-slate-100 bg-white p-3"
        >
          <span
            aria-hidden="true"
            className={cn(
              'mt-1.5 h-2 w-2 shrink-0 rounded-full',
              SEVERITY_DOT[gap.severity]
            )}
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-slate-900">{gap.area}</p>
              <span
                className={cn(
                  'rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide',
                  SEVERITY_LABEL_CLASS[gap.severity]
                )}
              >
                {gap.severity}
              </span>
            </div>
            <p className="mt-0.5 text-sm text-slate-600">{gap.description}</p>
          </div>
        </li>
      ))}
    </ul>
  )
}
