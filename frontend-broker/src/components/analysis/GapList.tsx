import type { components } from '@/api/types'
import { cn } from '@/lib/utils'

type CoverageGap = components['schemas']['CoverageGap']
type Severity = CoverageGap['severity']
type Basis = CoverageGap['basis']

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

/** Where each gap comes from: "not captured" is something to confirm, not a fact. */
const BASIS_TAG: Record<Basis, { label: string; title: string; className: string }> = {
  confirmed_in_document: {
    label: 'In document',
    title: 'Backed by a verified fact or exclusion in the policy document.',
    className: 'text-emerald-700 bg-emerald-50 border-emerald-200',
  },
  not_captured: {
    label: 'Not captured · confirm',
    title: 'The document extraction does not mention this. The policy may still have it, so confirm with the client.',
    className: 'text-slate-600 bg-white border-slate-300 border-dashed',
  },
  client_profile: {
    label: 'From chat',
    title: 'Based on what the prospect told us in the chat, not on a document.',
    className: 'text-brand-700 bg-brand-50 border-brand-100',
  },
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
            <p className="break-words text-sm font-medium text-slate-900">
              {gap.area.replace(/_/g, ' ')}
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <span
                className={cn(
                  'rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide',
                  SEVERITY_LABEL_CLASS[gap.severity]
                )}
              >
                {gap.severity}
              </span>
              <span
                title={BASIS_TAG[gap.basis ?? 'not_captured'].title}
                className={cn(
                  'rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide',
                  BASIS_TAG[gap.basis ?? 'not_captured'].className
                )}
              >
                {BASIS_TAG[gap.basis ?? 'not_captured'].label}
              </span>
            </div>
            <p className="mt-1.5 break-words text-sm text-slate-600">{gap.description}</p>
          </div>
        </li>
      ))}
    </ul>
  )
}
