import { AlertTriangle } from 'lucide-react'
import type { components } from '@/api/types'
import { cn } from '@/lib/utils'

type RiskFlag = components['schemas']['RiskFlag']
type Severity = RiskFlag['severity']

export interface RiskFlagListProps {
  flags: RiskFlag[]
}

const SEVERITY_ICON: Record<Severity, string> = {
  high: 'text-red-500',
  medium: 'text-amber-500',
  low: 'text-slate-400',
}

const SEVERITY_LABEL_CLASS: Record<Severity, string> = {
  high: 'text-red-700 bg-red-50 border-red-200',
  medium: 'text-amber-800 bg-amber-50 border-amber-200',
  low: 'text-slate-600 bg-slate-50 border-slate-200',
}

/** Humanise snake_case flag labels for display. */
const humanise = (slug: string): string =>
  slug.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

export function RiskFlagList({ flags }: RiskFlagListProps) {
  if (flags.length === 0) {
    return <p className="text-sm text-slate-500">No risk flags raised.</p>
  }
  return (
    <ul className="space-y-2">
      {flags.map((flag, i) => (
        <li
          key={`${flag.flag}-${i}`}
          className="flex items-start gap-3 rounded-lg border border-slate-100 bg-white p-3"
        >
          <AlertTriangle
            className={cn('mt-0.5 h-4 w-4 shrink-0', SEVERITY_ICON[flag.severity])}
            aria-hidden="true"
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-slate-900">
                {humanise(flag.flag)}
              </p>
              <span
                className={cn(
                  'rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide',
                  SEVERITY_LABEL_CLASS[flag.severity]
                )}
              >
                {flag.severity}
              </span>
            </div>
            <p className="mt-0.5 text-sm text-slate-600">{flag.description}</p>
          </div>
        </li>
      ))}
    </ul>
  )
}
